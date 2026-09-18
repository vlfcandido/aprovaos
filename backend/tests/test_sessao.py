# O que é: testes do passo 11 da V1 — token de sessão, assinatura HMAC do cookie, atributos do
# cookie e dependências `usuario_atual`/`exigir_usuario`. Quando ler: ao mexer em login/logout.
import hashlib
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, FastAPI, Response
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.api.sessao import (
    NOME_COOKIE,
    assinar,
    definir_cookie,
    exigir_usuario,
    limpar_cookie,
    usuario_atual,
    verificar_assinatura,
)
from aprovaos.config import Configuracoes
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Sessao, Usuario
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dados.repositorio_sessao import abrir_sessao, revogar_sessao, usuario_da_sessao
from aprovaos.dominio.conta import DadosCadastro

CHAVE = "c" * 32


def _usuario(db: Session) -> Usuario:
    usuario = criar_conta(db, DadosCadastro(email="linda@exemplo.com", senha="12345678"))
    db.commit()
    return usuario


def test_assinar_e_verificar() -> None:
    valor = assinar("tok", CHAVE)
    assert valor.startswith("tok.")
    assert verificar_assinatura(valor, CHAVE) == "tok"
    assert verificar_assinatura("tok.deadbeef", CHAVE) is None
    assert verificar_assinatura("tok", CHAVE) is None
    assert verificar_assinatura("", CHAVE) is None
    assert verificar_assinatura(valor, "d" * 32) is None


def test_abrir_sessao_grava_hash_e_nao_o_token(db: Session) -> None:
    usuario = _usuario(db)
    agora = agora_utc()
    token = abrir_sessao(db, usuario, dias=30, agora=agora)
    db.commit()
    linha = db.scalars(select(Sessao).where(Sessao.usuario_id == usuario.id)).one()
    assert linha.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert linha.token_hash != token
    assert linha.expira_em == agora + timedelta(days=30)
    assert linha.revogada_em is None


def test_usuario_da_sessao(db: Session) -> None:
    usuario = _usuario(db)
    agora = agora_utc()
    token = abrir_sessao(db, usuario, dias=30, agora=agora)
    db.commit()
    assert usuario_da_sessao(db, token, agora) is usuario
    assert usuario_da_sessao(db, token, agora + timedelta(days=30, seconds=1)) is None
    assert usuario_da_sessao(db, "desconhecido", agora) is None
    revogar_sessao(db, token, agora)
    db.commit()
    assert usuario_da_sessao(db, token, agora) is None


def test_revogar_sessao(db: Session) -> None:
    usuario = _usuario(db)
    agora = agora_utc()
    token = abrir_sessao(db, usuario, dias=30, agora=agora)
    db.commit()
    revogar_sessao(db, token, agora)
    db.commit()
    linha = db.scalars(select(Sessao).where(Sessao.usuario_id == usuario.id)).one()
    assert linha.revogada_em == agora
    # Idempotente: segunda chamada não estoura nem muda o instante; token desconhecido idem.
    revogar_sessao(db, token, agora + timedelta(hours=1))
    revogar_sessao(db, "desconhecido", agora)
    db.commit()
    assert linha.revogada_em == agora


def test_cookie_de_sessao(config_teste: Configuracoes) -> None:
    seguro = config_teste.model_copy(update={"cookie_seguro": True})
    resposta = Response()
    definir_cookie(resposta, "valor", seguro)
    cabecalho = resposta.headers["set-cookie"]
    assert f"{NOME_COOKIE}=valor" in cabecalho
    assert "HttpOnly" in cabecalho
    assert "Secure" in cabecalho
    assert "SameSite=lax" in cabecalho
    assert "Path=/" in cabecalho
    assert "Max-Age=2592000" in cabecalho

    resposta = Response()
    definir_cookie(resposta, "valor", config_teste)
    assert "Secure" not in resposta.headers["set-cookie"]

    resposta = Response()
    limpar_cookie(resposta, config_teste)
    cabecalho = resposta.headers["set-cookie"]
    assert f"{NOME_COOKIE}=" in cabecalho
    assert "Max-Age=0" in cabecalho
    assert "HttpOnly" in cabecalho
    assert "Path=/" in cabecalho


def _registrar_rotas(app: FastAPI) -> None:
    @app.get("/_quem")
    def _quem(usuario: Annotated[Usuario | None, Depends(usuario_atual)]) -> dict[str, str | None]:
        return {"email": usuario.email if usuario else None}

    @app.get("/_protegida")
    def _protegida(usuario: Annotated[Usuario, Depends(exigir_usuario)]) -> dict[str, str]:
        return {"email": usuario.email}


def test_usuario_atual_sem_cookie(app: FastAPI, cliente: TestClient) -> None:
    _registrar_rotas(app)
    assert cliente.get("/_quem").json() == {"email": None}
    cliente.cookies.set(NOME_COOKIE, "abc.def")
    assert cliente.get("/_quem").json() == {"email": None}


def test_usuario_atual_com_cookie_valido(
    app: FastAPI, cliente: TestClient, db: Session, config_teste: Configuracoes
) -> None:
    _registrar_rotas(app)
    usuario = _usuario(db)
    token = abrir_sessao(db, usuario, dias=30, agora=agora_utc())
    db.commit()
    cliente.cookies.set(NOME_COOKIE, assinar(token, config_teste.chave_secreta.get_secret_value()))
    assert cliente.get("/_quem").json() == {"email": "linda@exemplo.com"}
    # Token assinado com a chave certa mas sem sessão no banco → anônimo.
    outro = assinar("inexistente", config_teste.chave_secreta.get_secret_value())
    cliente.cookies.set(NOME_COOKIE, outro)
    assert cliente.get("/_quem").json() == {"email": None}


def test_exigir_usuario_redireciona_para_entrar(app: FastAPI, cliente: TestClient) -> None:
    _registrar_rotas(app)
    resposta = cliente.get("/_protegida", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"
