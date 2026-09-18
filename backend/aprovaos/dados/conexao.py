"""Fábricas de `Engine` e de `Session`: o único lugar que chama `create_engine`.

O que é: `criar_engine(url)` e `criar_fabrica_sessao(engine)`. Quando ler: ao ligar a app ou um
script ao banco — nunca crie engine em nível de módulo (`scripts/checar_import.py` proíbe).
"""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def criar_engine(url: str) -> Engine:
    """Cria o `Engine` para a URL dada, sem abrir conexão (o engine é preguiçoso).

    Args:
        url: URL SQLAlchemy (`sqlite://…`, `postgresql+psycopg://…`).

    Returns:
        Engine com `pool_pre_ping=True` (reconecta em conexão morta do pool).
    """
    return create_engine(url, pool_pre_ping=True)


def criar_fabrica_sessao(engine: Engine) -> sessionmaker[Session]:
    """Cria a fábrica de sessões ligada ao engine.

    Args:
        engine: engine criado por `criar_engine`.

    Returns:
        `sessionmaker` com `expire_on_commit=False`, para que objetos sigam legíveis após
        o `commit` feito pela rota.
    """
    return sessionmaker(bind=engine, expire_on_commit=False)
