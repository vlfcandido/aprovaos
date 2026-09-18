"""Hash e verificação de senha com argon2id (função pura, sem I/O).

O que é: `gerar_hash(senha)` e `verificar(hash, senha)` sobre `argon2.PasswordHasher`. Quando ler:
ao mudar parâmetros do argon2 ou ao precisar de re-hash quando os parâmetros evoluírem.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# Objeto puro: só guarda parâmetros (padrões da RFC 9106, perfil de baixa memória).
_HASHER = PasswordHasher()


def gerar_hash(senha: str) -> str:
    """Gera o hash argon2id da senha com sal aleatório.

    Args:
        senha: senha em texto claro, já validada pelo esquema de cadastro.

    Returns:
        Hash codificado (`$argon2id$…`), único a cada chamada por causa do sal.
    """
    return _HASHER.hash(senha)


def verificar(hash_: str, senha: str) -> bool:
    """Confere a senha contra o hash sem levantar exceção.

    Args:
        hash_: hash gravado em `usuario.senha_hash`.
        senha: senha informada no login.

    Returns:
        `True` só se a senha bater; `False` para senha errada ou hash malformado
        (`VerificationError` e `InvalidHashError`, conforme a doc do `PasswordHasher.verify`).
    """
    try:
        return _HASHER.verify(hash_, senha)
    except (VerificationError, InvalidHashError):
        return False
