"""Esquemas Pydantic dos formulários de conta (fronteira HTML → domínio).

O que é: `DadosCadastro` (senha 8–128) e `DadosLogin` (senha não vazia), ambos com e-mail
normalizado em minúsculas. Quando ler: ao mudar a política de senha ou acrescentar campo ao
formulário de conta.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator


class DadosCadastro(BaseModel):
    """Dados válidos de um cadastro por e-mail+senha.

    Attributes:
        email: e-mail sintaticamente válido, guardado em minúsculas.
        senha: entre 8 e 128 caracteres, sem outras regras (plano V1, Q2).
    """

    email: EmailStr
    senha: str = Field(min_length=8, max_length=128)

    @field_validator("email", mode="after")
    @classmethod
    def _minusculas(cls, valor: str) -> str:
        return valor.lower()


class DadosLogin(BaseModel):
    """Dados de um pedido de login; a política de tamanho é só `min_length=1`.

    Attributes:
        email: e-mail sintaticamente válido, guardado em minúsculas.
        senha: qualquer texto não vazio (a verificação real é contra o hash).
    """

    email: EmailStr
    senha: str = Field(min_length=1)

    @field_validator("email", mode="after")
    @classmethod
    def _minusculas(cls, valor: str) -> str:
        return valor.lower()
