# O que é: testes do passo 13 da V1 — rotas `GET/POST /entrar` (login com mensagem genérica em
# falha, cookie no sucesso, sessão nova a cada login). Quando ler: ao mexer em `api/conta.py`.
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Sessao, Usuario
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dominio.conta import DadosCadastro

MENSAGEM_GENERICA = "E-mail ou senha inválidos"


def _conta(db: Session) -> Usuario:
    usuario = criar_conta(db, DadosCadastro(email="linda@exemplo.com", senha="12345678"))
    db.commit()
    return usuario


def test_get_entrar(cliente: TestClient) -> None:
    resposta = cliente.get("/entrar")
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "<form" in corpo
    assert 'method="post"' in corpo
    assert 'name="email"' in corpo
    assert 'name="senha"' in corpo
    assert 'autocomplete="current-password"' in corpo
    assert 'hx-post="/entrar"' in corpo
    assert 'hx-select="#form-entrar"' in corpo
    assert 'hx-target="#form-entrar"' in corpo


def test_post_entrar_ok(cliente: TestClient, db: Session) -> None:
    _conta(db)
    dados = {"email": "Linda@Exemplo.com", "senha": "12345678"}
    resposta = cliente.post("/entrar", data=dados, follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/conta"
    cookie = resposta.headers["set-cookie"]
    assert "sessao=" in cookie
    assert "HttpOnly" in cookie

    resposta = cliente.post(
        "/entrar", data=dados, headers={"HX-Request": "true"}, follow_redirects=False
    )
    assert resposta.status_code == 200
    assert resposta.headers["hx-redirect"] == "/conta"
    assert "sessao=" in resposta.headers["set-cookie"]


def test_post_entrar_senha_errada(cliente: TestClient, db: Session) -> None:
    _conta(db)
    resposta = cliente.post(
        "/entrar", data={"email": "linda@exemplo.com", "senha": "errada123"}, follow_redirects=False
    )
    assert resposta.status_code == 200
    assert MENSAGEM_GENERICA in resposta.text
    assert "set-cookie" not in resposta.headers


def test_post_entrar_email_inexistente(cliente: TestClient, db: Session) -> None:
    _conta(db)
    dados = {"email": "ninguem@exemplo.com", "senha": "12345678"}
    resposta = cliente.post("/entrar", data=dados, follow_redirects=False)
    assert resposta.status_code == 200
    assert MENSAGEM_GENERICA in resposta.text
    assert "set-cookie" not in resposta.headers


def test_post_entrar_email_invalido_mesma_mensagem(cliente: TestClient) -> None:
    resposta = cliente.post(
        "/entrar", data={"email": "sem-arroba", "senha": "x"}, follow_redirects=False
    )
    assert resposta.status_code == 200
    assert MENSAGEM_GENERICA in resposta.text
    assert "set-cookie" not in resposta.headers


def test_cada_login_abre_sessao_nova(cliente: TestClient, db: Session) -> None:
    usuario = _conta(db)
    dados = {"email": "linda@exemplo.com", "senha": "12345678"}
    cliente.post("/entrar", data=dados, follow_redirects=False)
    cliente.post("/entrar", data=dados, follow_redirects=False)
    consulta = select(func.count()).select_from(Sessao).where(Sessao.usuario_id == usuario.id)
    total = db.scalar(consulta)
    assert total == 2
