"""Base declarativa do ORM, tipo de data/hora sempre UTC e mixins de chave e carimbos.

O que é: `Base`, `DataHoraUtc`, `ChaveUuid`, `Carimbos`, `agora_utc()`. Quando ler: ao criar
qualquer modelo novo — todos herdam daqui; a convenção de nomes é o que o Alembic usa.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData, Uuid
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

CONVENCAO_DE_NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def agora_utc() -> datetime:
    """Devolve o instante atual como `datetime` *aware* em UTC.

    Returns:
        `datetime.now(UTC)`; é a única fonte de "agora" da camada de dados.
    """
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base declarativa de todos os modelos, com convenção de nomes para constraints."""

    metadata = MetaData(naming_convention=CONVENCAO_DE_NOMES)


class DataHoraUtc(TypeDecorator[datetime]):
    """`DateTime(timezone=True)` que grava em UTC e devolve sempre *aware*.

    O SQLite descarta o fuso e devolve `datetime` naive; sem este decorador, comparar
    `expira_em < agora` levantaria `TypeError`. No Postgres (`timestamptz`) é transparente.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Converte o valor para UTC antes de gravar; exige `datetime` aware.

        Args:
            value: data/hora a gravar (ou `None`).
            dialect: dialeto ativo (não usado).

        Returns:
            O mesmo instante em UTC, ou `None`.

        Raises:
            TypeError: se o valor for naive (sem `tzinfo`).
        """
        if value is None:
            return None
        if value.tzinfo is None:
            raise TypeError("DataHoraUtc exige datetime aware (com tzinfo)")
        return value.astimezone(UTC)

    def process_result_value(self, value: Any | None, dialect: Dialect) -> datetime | None:
        """Garante `tzinfo=UTC` no valor lido, mesmo quando o banco devolve naive.

        Args:
            value: valor devolvido pelo driver (ou `None`).
            dialect: dialeto ativo (não usado).

        Returns:
            `datetime` aware em UTC, ou `None`.
        """
        if value is None:
            return None
        if not isinstance(value, datetime):
            raise TypeError(f"DataHoraUtc esperava datetime, recebeu {type(value).__name__}")
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class ChaveUuid:
    """Mixin: chave primária `id` UUID (v4; trocar por v7 quando o Python pinado permitir)."""

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)


class Carimbos:
    """Mixin: `criado_em` e `atualizado_em` em UTC, preenchidos pela aplicação."""

    criado_em: Mapped[datetime] = mapped_column(DataHoraUtc, default=agora_utc, nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(
        DataHoraUtc, default=agora_utc, onupdate=agora_utc, nullable=False
    )
