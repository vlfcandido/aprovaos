# O que é: testes do passo 10 da V1 — cadastro cria tenant PF + usuário; autenticação genérica.
# Quando ler: ao mudar as regras de criação de conta ou de login no repositório.
import pytest
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.repositorio_conta import autenticar, buscar_por_email, criar_conta
from aprovaos.dominio.conta import DadosCadastro, DadosLogin
from aprovaos.dominio.erros import CredenciaisInvalidas, EmailJaCadastrado


def test_criar_conta_cria_tenant_pf(db: Session) -> None:
    usuario = criar_conta(db, DadosCadastro(email="Linda@Exemplo.com", senha="12345678"))
    db.commit()
    assert usuario.tenant.tipo == "pf"
    assert usuario.tenant.nome == "linda@exemplo.com"
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
