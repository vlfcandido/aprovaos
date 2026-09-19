# O que é: migração da fatia 12 — cria `assinatura` (RF-22, uma por usuário) e `evento_cobranca`
# (append-only, o corpo cru de cada webhook do gateway de pagamento). Quando ler: nunca editar
# depois de aplicada; mudanças de esquema entram em migração nova.
"""assinatura

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-19

`assinatura` espelha `dominio.assinatura.Tier`/`StatusAssinatura` — ver o docstring da classe
`Assinatura` em `aprovaos/dados/modelos.py` para o porquê de cada coluna (em especial `fim`, que
`dominio.assinatura.tier_efetivo` usa para decidir se uma assinatura cancelada/em atraso ainda
vale como Pro). `evento_cobranca` é o registro cru de cada webhook recebido, para auditoria —
"dinheiro exige rastro" (plano `docs/fatias/12-billing.md` §3).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `assinatura` e `evento_cobranca`."""
    op.create_table(
        "assinatura",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("tier", sa.String(length=8), nullable=False),
        sa.Column("periodicidade", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fim", sa.Date(), nullable=False),
        sa.Column("gateway", sa.String(length=24), nullable=False),
        sa.Column("id_externo", sa.String(length=120), nullable=False),
        sa.Column("cancelada_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tier IN ('free','pro')", name=op.f("ck_assinatura_tier")),
        sa.CheckConstraint(
            "status IN ('ativa','em_atraso','cancelada','expirada')",
            name=op.f("ck_assinatura_status"),
        ),
        sa.CheckConstraint(
            "periodicidade IN ('mensal','anual')", name=op.f("ck_assinatura_periodicidade")
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"], name=op.f("fk_assinatura_usuario_id_usuario")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assinatura")),
        sa.UniqueConstraint("usuario_id", name=op.f("uq_assinatura_usuario_id")),
    )
    with op.batch_alter_table("assinatura", schema=None) as batch_op:
        batch_op.create_index("ix_assinatura_usuario_id", ["usuario_id"], unique=False)

    op.create_table(
        "evento_cobranca",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gateway", sa.String(length=24), nullable=False),
        sa.Column("id_externo", sa.String(length=120), nullable=False),
        sa.Column("tipo", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("recebido_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processado_em", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evento_cobranca")),
    )


def downgrade() -> None:
    """Remove `evento_cobranca` e `assinatura`."""
    op.drop_table("evento_cobranca")
    with op.batch_alter_table("assinatura", schema=None) as batch_op:
        batch_op.drop_index("ix_assinatura_usuario_id")
    op.drop_table("assinatura")
