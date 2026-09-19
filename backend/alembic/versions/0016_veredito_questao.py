# O que é: migração da fatia 5 — cria `veredito_questao` (histórico append-only das tentativas
# de validação de uma inédita, RF-28). Quando ler: nunca editar depois de aplicada; mudanças de
# esquema entram em migração nova.
"""veredito_questao

Revision ID: 0016
Revises: 0014
Create Date: 2026-09-19

`veredito_questao` guarda uma linha por chamada a `dominio.validacao_questao.julgar` sobre uma
`Questao` inédita — ver o docstring da classe `VereditoQuestao` em `aprovaos/dados/modelos.py`.
Não mexe em `questao`: `origem` (nullable), `inedita`, `validada_em`, `validador_versao`,
`justificativa_certo`/`justificativa_errado` já existiam desde a V3/fundação jurídica.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `veredito_questao`."""
    op.create_table(
        "veredito_questao",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("questao_id", sa.Uuid(), nullable=False),
        sa.Column("aprovado", sa.Boolean(), nullable=False),
        sa.Column("motivos", sa.JSON(), nullable=False),
        sa.Column("validador_versao", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_veredito_questao")),
        sa.ForeignKeyConstraint(
            ["questao_id"],
            ["questao.id"],
            name=op.f("fk_veredito_questao_questao_id_questao"),
        ),
    )
    with op.batch_alter_table("veredito_questao", schema=None) as batch_op:
        batch_op.create_index("ix_veredito_questao_questao_id", ["questao_id"], unique=False)


def downgrade() -> None:
    """Remove `veredito_questao`."""
    with op.batch_alter_table("veredito_questao", schema=None) as batch_op:
        batch_op.drop_index("ix_veredito_questao_questao_id")
    op.drop_table("veredito_questao")
