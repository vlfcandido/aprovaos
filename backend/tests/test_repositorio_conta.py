# O que é: testes do passo 10 da V1 — cadastro cria tenant PF + usuário; autenticação genérica.
# Quando ler: ao mudar as regras de criação de conta ou de login no repositório.
import pytest
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.repositorio_conta import (
    autenticar,
    buscar_por_email,
    criar_conta,
    criar_ou_ligar_conta_google,
)
from aprovaos.dominio.conta import DadosCadastro, DadosLogin
from aprovaos.dominio.erros import CredenciaisInvalidas, EmailJaCadastrado


def test_criar_conta_cria_tenant_pf(db: Session) -> None:
    usuario = criar_conta(db, DadosCadastro(email="Linda@Exemplo.com", senha="12345678"))
    db.commit()
    assert usuario.tenant.tipo == "pf"
    assert usuario.tenant.nome == "linda@exemplo.com"
    assert usuario.senha_hash is not None
    assert usuario.senha_hash.startswith("$argon2id$")
    assert usuario.email == "linda@exemplo.com"
    assert buscar_por_email(db, "linda@exemplo.com") is usuario
    assert buscar_por_email(db, "ninguem@exemplo.com") is None


def test_criar_conta_email_repetido(db: Session) -> None:
    dados = DadosCadastro(email="linda@exemplo.com", senha="12345678")
    criar_conta(db, dados)
    db.commit()
    with pytest.raises(EmailJaCadastrado):
        criar_conta(db, dados)


def test_autenticar(db: Session) -> None:
    usuario = criar_conta(db, DadosCadastro(email="linda@exemplo.com", senha="12345678"))
    db.commit()
    assert autenticar(db, DadosLogin(email="Linda@Exemplo.com", senha="12345678")) is usuario
    with pytest.raises(CredenciaisInvalidas):
        autenticar(db, DadosLogin(email="linda@exemplo.com", senha="errada"))
    with pytest.raises(CredenciaisInvalidas):
        autenticar(db, DadosLogin(email="ninguem@exemplo.com", senha="12345678"))
    usuario.excluido_em = agora_utc()
    db.commit()
    with pytest.raises(CredenciaisInvalidas):
        autenticar(db, DadosLogin(email="linda@exemplo.com", senha="12345678"))


def test_criar_ou_ligar_conta_google_cria_conta_sem_senha(db: Session) -> None:
    usuario = criar_ou_ligar_conta_google(db, "g-1", "nova@exemplo.com")
    db.commit()
    assert usuario.senha_hash is None
    assert usuario.google_sub == "g-1"
    assert usuario.tenant.tipo == "pf"


def test_criar_ou_ligar_conta_google_liga_conta_existente(db: Session) -> None:
    original = criar_conta(db, DadosCadastro(email="linda@exemplo.com", senha="12345678"))
    db.commit()

    ligada = criar_ou_ligar_conta_google(db, "g-2", "linda@exemplo.com")
    db.commit()

    assert ligada.id == original.id
    assert ligada.google_sub == "g-2"
    assert ligada.senha_hash is not None  # a senha original não é apagada


def test_criar_ou_ligar_conta_google_e_idempotente(db: Session) -> None:
    primeira = criar_ou_ligar_conta_google(db, "g-3", "outra@exemplo.com")
    db.commit()
    segunda = criar_ou_ligar_conta_google(db, "g-3", "outra@exemplo.com")
    db.commit()
    assert primeira.id == segunda.id


def test_autenticar_conta_so_google_nunca_bate_senha(db: Session) -> None:
    criar_ou_ligar_conta_google(db, "g-4", "sogoogle@exemplo.com")
    db.commit()
    with pytest.raises(CredenciaisInvalidas):
        autenticar(db, DadosLogin(email="sogoogle@exemplo.com", senha="qualquer-coisa"))
