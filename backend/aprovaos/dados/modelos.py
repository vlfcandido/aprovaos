"""Modelos ORM: tabelas base da V1 (`tenant`, `usuario`, `sessao`, `traco`) e de edital/DNA da V2.

O que é: as dez tabelas do AprovaOS até a V2 (modelo de dados §2, §3 e §4). Quando ler: ao
consultar ou estender essas tabelas; nomes de tabela e coluna são os de
`docs/04-modelo-de-dados.md` — não renomeie. `dna_concurso` guarda o JSON inteiro do DNA em
`conteudo` (plano V2, premissa B) e `topico_edital.ordem` dá a posição do tópico no edital.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
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


class Concurso(ChaveUuid, Carimbos, Base):
    """Concurso de um tenant (`tenant_id` `NULL` = catálogo futuro, fatia 1b).

    `banca` recebe `"desconhecido"` quando o edital não a declara — nunca `NULL`, para o DNA
    e a página terem um único jeito de dizer "não sei".
    """

    __tablename__ = "concurso"

    tenant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tenant.id"), index=True, nullable=True
    )
    orgao: Mapped[str] = mapped_column(String(200), nullable=False)
    cargo: Mapped[str] = mapped_column(String(200), nullable=False)
    banca: Mapped[str] = mapped_column(String(200), nullable=False)
    data_prova: Mapped[date | None] = mapped_column(Date, nullable=True)

    tenant: Mapped[Tenant | None] = relationship()


class Documento(ChaveUuid, Carimbos, Base):
    """Arquivo bruto guardado em disco (edital subido, prova, gabarito…), endereçado pelo hash."""

    __tablename__ = "documento"
    __table_args__ = (
        CheckConstraint("tipo IN ('prova','gabarito','edital','lei','informativo')", name="tipo"),
    )

    tipo: Mapped[str] = mapped_column(String(16), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    caminho: Mapped[str] = mapped_column(String(255), nullable=False)
    baixado_em: Mapped[datetime] = mapped_column(DataHoraUtc, nullable=False)
    metadados: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Edital(ChaveUuid, Carimbos, Base):
    """Versão de edital de um concurso (`versao` 1 na V2; retificações viram versão 2, P-24)."""

    __tablename__ = "edital"
    __table_args__ = (UniqueConstraint("concurso_id", "versao"),)

    concurso_id: Mapped[UUID] = mapped_column(ForeignKey("concurso.id"), index=True, nullable=False)
    versao: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    documento_id: Mapped[UUID] = mapped_column(ForeignKey("documento.id"), nullable=False)

    concurso: Mapped[Concurso] = relationship()
    documento: Mapped[Documento] = relationship()


class Topico(ChaveUuid, Carimbos, Base):
    """Vocabulário global de tópicos por `slug` (get-or-create; compartilhado entre editais)."""

    __tablename__ = "topico"

    materia: Mapped[str] = mapped_column(String(120), nullable=False)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)


class TopicoEdital(ChaveUuid, Carimbos, Base):
    """Tópico como aparece num edital: texto original, posição (`ordem`) e peso uniforme."""

    __tablename__ = "topico_edital"
    __table_args__ = (UniqueConstraint("edital_id", "topico_id"),)

    edital_id: Mapped[UUID] = mapped_column(ForeignKey("edital.id"), index=True, nullable=False)
    topico_id: Mapped[UUID] = mapped_column(ForeignKey("topico.id"), nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    peso_edital: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    texto_original: Mapped[str] = mapped_column(Text, nullable=False)

    edital: Mapped[Edital] = relationship()
    topico: Mapped[Topico] = relationship()


class DnaConcursoRegistro(ChaveUuid, Carimbos, Base):
    """Linha de `dna_concurso`: o JSON inteiro do `DnaConcurso` em `conteudo` + origem/versão.

    O nome Python evita colidir com o modelo Pydantic `DnaConcurso` de `dominio/dna.py`.
    """

    __tablename__ = "dna_concurso"
    __table_args__ = (
        UniqueConstraint("concurso_id", "versao"),
        CheckConstraint("origem IN ('ia','regras')", name="origem"),
    )

    concurso_id: Mapped[UUID] = mapped_column(ForeignKey("concurso.id"), index=True, nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    gerado_em: Mapped[datetime] = mapped_column(DataHoraUtc, nullable=False)
    origem: Mapped[str] = mapped_column(String(8), nullable=False)
    modelo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    motivo_fallback: Mapped[str | None] = mapped_column(Text, nullable=True)
    conteudo: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    concurso: Mapped[Concurso] = relationship()
