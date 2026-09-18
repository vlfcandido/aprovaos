"""Modelos ORM da V1: `tenant`, `usuario`, `sessao` e `traco` (modelo de dados §2 e §4).

O que é: as quatro tabelas base do AprovaOS. Quando ler: ao consultar ou estender essas
tabelas; nomes de tabela e coluna são os de `docs/04-modelo-de-dados.md` — não renomeie.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aprovaos.dados.base import Base, Carimbos, ChaveUuid, DataHoraUtc, agora_utc


class Tenant(ChaveUuid, Carimbos, Base):
    """Dono dos dados: pessoa física (`pf`, criado no cadastro) ou organização (`org`)."""

    __tablename__ = "tenant"
    __table_args__ = (CheckConstraint("tipo IN ('pf','org')", name="tipo"),)

    tipo: Mapped[str] = mapped_column(String(8), nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)


class Usuario(ChaveUuid, Carimbos, Base):
    """Conta de acesso por e-mail+senha (argon2); `excluido_em` marca pedido de exclusão."""

    __tablename__ = "usuario"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.id"), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    excluido_em: Mapped[datetime | None] = mapped_column(DataHoraUtc, nullable=True)

    tenant: Mapped[Tenant] = relationship()


class Sessao(ChaveUuid, Carimbos, Base):
    """Sessão de login server-side (ADR-0026): guarda só o SHA-256 do token do cookie."""

    __tablename__ = "sessao"

    usuario_id: Mapped[UUID] = mapped_column(ForeignKey("usuario.id"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DataHoraUtc, nullable=False)
    revogada_em: Mapped[datetime | None] = mapped_column(DataHoraUtc, nullable=True)

    usuario: Mapped[Usuario] = relationship()


class Traco(ChaveUuid, Base):
    """Traço de execução de agente (ADR-0024): fonte de custos; sem escrita na V1."""

    __tablename__ = "traco"

    criado_em: Mapped[datetime] = mapped_column(DataHoraUtc, default=agora_utc, nullable=False)
    iniciado_em: Mapped[datetime] = mapped_column(DataHoraUtc, nullable=False)
    duracao_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    usuario_id: Mapped[UUID | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    agente: Mapped[str] = mapped_column(String(64), nullable=False)
    modelo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custo_brl: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    tier: Mapped[str | None] = mapped_column(String(8), nullable=True)
    resultado: Mapped[str] = mapped_column(String(16), nullable=False)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    span_pai_id: Mapped[UUID | None] = mapped_column(ForeignKey("traco.id"), nullable=True)
