"""Repositório de sessão de login server-side (ADR-0026): abre, consulta e revoga.

O que é: `abrir_sessao`, `usuario_da_sessao`, `revogar_sessao`. O banco guarda só o SHA-256 do
token; o token em claro vive apenas no cookie. Quando ler: ao mexer em login, logout ou na
validade da sessão. As funções fazem `add`/`flush`; o `commit` é da rota.
"""

import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Sessao, Usuario


def _hash_do_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _sessao_pelo_token(db: Session, token: str) -> Sessao | None:
    return db.scalars(select(Sessao).where(Sessao.token_hash == _hash_do_token(token))).first()


def abrir_sessao(db: Session, usuario: Usuario, dias: int, agora: datetime) -> str:
    """Cria uma sessão nova para o usuário e devolve o token em claro (vai só para o cookie).

    Args:
        db: sessão do request.
        usuario: usuário autenticado.
        dias: validade em dias (`Configuracoes.sessao_dias`).
        agora: instante de referência, aware em UTC.

    Returns:
        Token aleatório (`secrets.token_urlsafe(32)`); no banco fica apenas o SHA-256.
    """
    token = secrets.token_urlsafe(32)
    sessao = Sessao(
        usuario=usuario, token_hash=_hash_do_token(token), expira_em=agora + timedelta(days=dias)
    )
    db.add(sessao)
    db.flush()
    return token


def usuario_da_sessao(db: Session, token: str, agora: datetime) -> Usuario | None:
    """Resolve o usuário de um token válido (existente, não expirado, não revogado).

    Args:
        db: sessão do request.
        token: token em claro vindo do cookie (já com assinatura verificada).
        agora: instante de referência, aware em UTC.

    Returns:
        O `Usuario` dono da sessão, ou `None` em qualquer outro caso.
    """
    sessao = _sessao_pelo_token(db, token)
    if sessao is None or sessao.revogada_em is not None or sessao.expira_em < agora:
        return None
    return sessao.usuario


def revogar_sessao(db: Session, token: str, agora: datetime) -> None:
    """Marca a sessão como revogada; idempotente e silenciosa para token desconhecido.

    Args:
        db: sessão do request.
        token: token em claro vindo do cookie.
        agora: instante gravado em `revogada_em` (só na primeira revogação).
    """
    sessao = _sessao_pelo_token(db, token)
    if sessao is None or sessao.revogada_em is not None:
        return
    sessao.revogada_em = agora
    db.flush()
