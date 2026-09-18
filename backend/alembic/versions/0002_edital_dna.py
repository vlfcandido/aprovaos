# O que é: migração da V2 — cria concurso, edital, documento, topico, topico_edital e
# dna_concurso (modelo de dados §3). Quando ler: nunca editar depois de aplicada.
"""edital_dna

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-17

Gerada por `alembic revision --autogenerate` e revisada: `DataHoraUtc` vira
`sa.DateTime(timezone=True)` (mesmo tipo no banco), `id` vem primeiro e as tabelas seguem a
ordem das dependências (documento, concurso, topico, edital, topico_edital, dna_concurso).
`dna_concurso.conteudo` guarda o JSON inteiro do DNA (plano V2, premissa B).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria as seis tabelas de edital e DNA."""
    op.create_table(
        "documento",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=16), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column("caminho", sa.String(length=255), nullable=False),
        sa.Column("baixado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadados", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('prova','gabarito','edital','lei','informativo')",
            name=op.f("ck_documento_tipo"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documento")),
    )
    with op.batch_alter_table("documento", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_documento_hash"), ["hash"], unique=False)

    op.create_table(
        "concurso",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("orgao", sa.String(length=200), nullable=False),
        sa.Column("cargo", sa.String(length=200), nullable=False),
        sa.Column("banca", sa.String(length=200), nullable=False),
        sa.Column("data_prova", sa.Date(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenant.id"], name=op.f("fk_concurso_tenant_id_tenant")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_concurso")),
    )
    with op.batch_alter_table("concurso", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_concurso_tenant_id"), ["tenant_id"], unique=False)

    op.create_table(
        "topico",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("materia", sa.String(length=120), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_topico")),
        sa.UniqueConstraint("slug", name=op.f("uq_topico_slug")),
    )

    op.create_table(
        "edital",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("concurso_id", sa.Uuid(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("documento_id", sa.Uuid(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["concurso_id"], ["concurso.id"], name=op.f("fk_edital_concurso_id_concurso")
        ),
        sa.ForeignKeyConstraint(
            ["documento_id"], ["documento.id"], name=op.f("fk_edital_documento_id_documento")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_edital")),
        sa.UniqueConstraint("concurso_id", "versao", name=op.f("uq_edital_concurso_id")),
    )
    with op.batch_alter_table("edital", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_edital_concurso_id"), ["concurso_id"], unique=False)

    op.create_table(
        "topico_edital",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("edital_id", sa.Uuid(), nullable=False),
        sa.Column("topico_id", sa.Uuid(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("peso_edital", sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column("texto_original", sa.Text(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["edital_id"], ["edital.id"], name=op.f("fk_topico_edital_edital_id_edital")
        ),
        sa.ForeignKeyConstraint(
            ["topico_id"], ["topico.id"], name=op.f("fk_topico_edital_topico_id_topico")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_topico_edital")),
        sa.UniqueConstraint("edital_id", "topico_id", name=op.f("uq_topico_edital_edital_id")),
    )
    with op.batch_alter_table("topico_edital", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_topico_edital_edital_id"), ["edital_id"], unique=False)

    op.create_table(
        "dna_concurso",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("concurso_id", sa.Uuid(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("gerado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("origem", sa.String(length=8), nullable=False),
        sa.Column("modelo", sa.String(length=64), nullable=True),
        sa.Column("motivo_fallback", sa.Text(), nullable=True),
        sa.Column("conteudo", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("origem IN ('ia','regras')", name=op.f("ck_dna_concurso_origem")),
        sa.ForeignKeyConstraint(
            ["concurso_id"], ["concurso.id"], name=op.f("fk_dna_concurso_concurso_id_concurso")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dna_concurso")),
        sa.UniqueConstraint("concurso_id", "versao", name=op.f("uq_dna_concurso_concurso_id")),
    )
    with op.batch_alter_table("dna_concurso", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_dna_concurso_concurso_id"), ["concurso_id"], unique=False
        )


def downgrade() -> None:
    """Remove as seis tabelas, na ordem inversa das dependências."""
    with op.batch_alter_table("dna_concurso", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_dna_concurso_concurso_id"))
    op.drop_table("dna_concurso")
    with op.batch_alter_table("topico_edital", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_topico_edital_edital_id"))
    op.drop_table("topico_edital")
    with op.batch_alter_table("edital", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_edital_concurso_id"))
    op.drop_table("edital")
    op.drop_table("topico")
    with op.batch_alter_table("concurso", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_concurso_tenant_id"))
    op.drop_table("concurso")
    with op.batch_alter_table("documento", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_documento_hash"))
    op.drop_table("documento")
