"""Cookie de sessão assinado (HMAC-SHA256 da stdlib) e dependências de usuário logado.

O que é: `assinar`/`verificar_assinatura`, `definir_cookie`/`limpar_cookie`, `usuario_atual`
(opcional) e `exigir_usuario` (redireciona para `/entrar` via `RedirecionarParaEntrar`).
Quando ler: ao escrever rota que precisa saber quem está logado, ou ao mexer em login/logout.
"""

import hashlib
import hmac
from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from aprovaos.api.db import obter_db
from aprovaos.config import Configuracoes
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Usuario
from aprovaos.dados.repositorio_sessao import usuario_da_sessao

NOME_COOKIE = "sessao"
SEGUNDOS_POR_DIA = 86400


class RedirecionarParaEntrar(Exception):
    """Levantada por `exigir_usuario` sem login; o tratador responde `303 /entrar`."""


def _assinatura(token: str, chave: str) -> str:
    return hmac.new(chave.encode(), token.encode(), hashlib.sha256).hexdigest()


def assinar(token: str, chave: str) -> str:
    """Monta o valor do cookie: `<token>.<hmac_sha256_hex>`.

    Args:
        token: token de sessão em claro.
        chave: `Configuracoes.chave_secreta` já sem `SecretStr`.

    Returns:
        O valor pronto para `definir_cookie`.
    """
    return f"{token}.{_assinatura(token, chave)}"


def verificar_assinatura(valor: str, chave: str) -> str | None:
    """Extrai o token de um valor de cookie se a assinatura bater (`hmac.compare_digest`).

    Args:
        valor: valor bruto do cookie.
        chave: a mesma chave usada em `assinar`.

    Returns:
        O token em claro, ou `None` para valor sem ponto, adulterado ou de outra chave.
    """
    token, separador, assinatura = valor.rpartition(".")
    if not separador or not token:
        return None
    if not hmac.compare_digest(_assinatura(token, chave), assinatura):
        return None
    return token


def definir_cookie(resposta: Response, valor: str, config: Configuracoes) -> None:
    """Grava o cookie de sessão com `HttpOnly`, `SameSite=lax`, `Path=/` e `Secure` conforme config.

    Args:
        resposta: resposta que levará o `Set-Cookie`.
        valor: saída de `assinar`.
        config: fonte de `cookie_seguro` e `sessao_dias`.
    """
    resposta.set_cookie(
        NOME_COOKIE,
        valor,
        max_age=config.sessao_dias * SEGUNDOS_POR_DIA,
        path="/",
        secure=config.cookie_seguro,
        httponly=True,
        samesite="lax",
    )


def limpar_cookie(resposta: Response, config: Configuracoes) -> None:
    """Remove o cookie de sessão (`Max-Age=0`) com os mesmos atributos de `definir_cookie`.

    Args:
        resposta: resposta que levará o `Set-Cookie` de expiração.
        config: fonte de `cookie_seguro`.
    """
    resposta.delete_cookie(
        NOME_COOKIE, path="/", secure=config.cookie_seguro, httponly=True, samesite="lax"
    )


def token_do_request(request: Request) -> str | None:
    """Lê o cookie de sessão e devolve o token em claro se a assinatura conferir.

    Args:
        request: requisição atual (usa `app.state.config.chave_secreta`).

    Returns:
        O token, ou `None` sem cookie ou com cookie inválido.
    """
    valor = request.cookies.get(NOME_COOKIE)
    if not valor:
        return None
    config: Configuracoes = request.app.state.config
    return verificar_assinatura(valor, config.chave_secreta.get_secret_value())


def usuario_atual(request: Request, db: Annotated[Session, Depends(obter_db)]) -> Usuario | None:
    """Dependência: o usuário logado, ou `None` (cookie ausente, adulterado, expirado, revogado).

    Args:
        request: requisição atual.
        db: sessão de banco do request.

    Returns:
        O `Usuario` da sessão válida, ou `None`.
    """
    token = token_do_request(request)
    if token is None:
        return None
    return usuario_da_sessao(db, token, agora_utc())


def exigir_usuario(usuario: Annotated[Usuario | None, Depends(usuario_atual)]) -> Usuario:
    """Dependência: o usuário logado, obrigatório.

    Args:
        usuario: resultado de `usuario_atual`.

    Returns:
        O `Usuario` logado.

    Raises:
        RedirecionarParaEntrar: sem login; vira `303 /entrar` pelo tratador registrado.
    """
    if usuario is None:
        raise RedirecionarParaEntrar()
    return usuario
