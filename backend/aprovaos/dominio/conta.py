"""Esquemas Pydantic dos formulários de conta e do perfil OpenID do Google (fronteira → domínio).

O que é: `DadosCadastro` (senha 8–128), `DadosLogin` (senha não vazia) e `PerfilGoogle` (fatia
1b, RF-20, Ruling 42 — o corpo do endpoint `userinfo` do Google, ver
https://developers.google.com/identity/openid-connect/openid-connect#obtaininguserprofileinformation),
todos com e-mail normalizado em minúsculas. Quando ler: ao mudar a política de senha, acrescentar
campo ao formulário de conta, ou mexer no que o login por Google exige do perfil.
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


class PerfilGoogle(BaseModel):
    """O corpo do endpoint `userinfo` do Google, só os campos que o login usa (Ruling 42).

    Attributes:
        sub: identidade estável da conta Google — nunca o e-mail (que pode mudar).
        email: e-mail da conta Google, normalizado em minúsculas.
        email_verified: `True` só quando o Google confirma que o e-mail é do dono da conta; a
            rota rejeita o login quando `False` (`dominio.erros.EmailGoogleNaoVerificado`).
    """

    sub: str
    email: EmailStr
    email_verified: bool

    @field_validator("email", mode="after")
    @classmethod
    def _minusculas(cls, valor: str) -> str:
        return valor.lower()
