# O que é: testes do passo 9 da V1 — esquemas Pydantic dos formulários de conta e erros de domínio.
# Quando ler: ao mudar a política de senha, a normalização de e-mail ou as exceções de conta.
import pytest
from pydantic import ValidationError

from aprovaos.dominio.conta import DadosCadastro, DadosLogin
from aprovaos.dominio.erros import CredenciaisInvalidas, EmailJaCadastrado, ErroDominio


def test_dados_cadastro_normaliza_email() -> None:
    dados = DadosCadastro(email="Linda@Exemplo.com", senha="12345678")
    assert dados.email == "linda@exemplo.com"


def test_dados_cadastro_rejeita() -> None:
    with pytest.raises(ValidationError):
        DadosCadastro(email="linda@exemplo.com", senha="1234567")
    with pytest.raises(ValidationError):
        DadosCadastro(email="linda@exemplo.com", senha="x" * 129)
    with pytest.raises(ValidationError):
        DadosCadastro(email="sem-arroba", senha="12345678")


def test_dados_login() -> None:
    dados = DadosLogin(email="Linda@Exemplo.com", senha="1")
    assert dados.email == "linda@exemplo.com"
    assert dados.senha == "1"
    with pytest.raises(ValidationError):
        DadosLogin(email="linda@exemplo.com", senha="")
    with pytest.raises(ValidationError):
        DadosLogin(email="sem-arroba", senha="1")


def test_erros_de_dominio() -> None:
    assert issubclass(ErroDominio, Exception)
    assert issubclass(EmailJaCadastrado, ErroDominio)
    assert issubclass(CredenciaisInvalidas, ErroDominio)
