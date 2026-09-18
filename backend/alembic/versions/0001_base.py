# O que é: migração inicial da V1 — cria tenant, usuario, sessao e traco (modelo de dados §2/§4).
# Quando ler: nunca editar depois de aplicada; mudanças de esquema entram em migração nova.
"""base

Revision ID: 0001
Revises:
Create Date: 2026-09-17

Gerada por `alembic revision --autogenerate` e revisada: `DataHoraUtc` vira
`sa.DateTime(timezone=True)` (mesmo tipo no banco) e `id` vem primeiro.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria as quatro tabelas base."""
    op.create_table(
        "tenant",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=8), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("tipo IN ('pf','org')", name=op.f("ck_tenant_tipo")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant")),
    )
    op.create_table(
        "usuario",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column("excluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenant.id"], name=op.f("fk_usuario_tenant_id_tenant")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usuario")),
        sa.UniqueConstraint("email", name=op.f("uq_usuario_email")),
    )
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_usuario_tenant_id"), ["tenant_id"], unique=False)

    op.create_table(
        "sessao",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revogada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"], name=op.f("fk_sessao_usuario_id_usuario")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessao")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessao_token_hash")),
    )
    with op.batch_alter_table("sessao", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_sessao_usuario_id"), ["usuario_id"], unique=False)

    op.create_table(
        "traco",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("iniciado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duracao_ms", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=True),
        sa.Column("agente", sa.String(length=64), nullable=False),
        sa.Column("modelo", sa.String(length=64), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("custo_brl", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("tier", sa.String(length=8), nullable=True),
        sa.Column("resultado", sa.String(length=16), nullable=False),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column("span_pai_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["span_pai_id"], ["traco.id"], name=op.f("fk_traco_span_pai_id_traco")
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"], name=op.f("fk_traco_usuario_id_usuario")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_traco")),
    )


def downgrade() -> None:
    """Remove as quatro tabelas base, na ordem inversa das dependências."""
    op.drop_table("traco")
    with op.batch_alter_table("sessao", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sessao_usuario_id"))
    op.drop_table("sessao")
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_usuario_tenant_id"))
    op.drop_table("usuario")
    op.drop_table("tenant")
