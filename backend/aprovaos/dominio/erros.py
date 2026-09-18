"""Exceções de domínio da conta (regras de negócio, independentes de HTTP e de banco).

O que é: `ErroDominio` e as subclasses `EmailJaCadastrado` e `CredenciaisInvalidas`. Quando ler:
ao tratar falhas esperadas de cadastro/login numa rota ou ao criar uma regra de domínio nova.
"""


class ErroDominio(Exception):
    """Raiz de todas as falhas esperadas do domínio; a rota decide como mostrar."""


class EmailJaCadastrado(ErroDominio):
    """Já existe conta ativa com este e-mail (cadastro)."""


class CredenciaisInvalidas(ErroDominio):
    """E-mail inexistente, senha errada ou conta excluída — sem distinguir qual (login)."""
