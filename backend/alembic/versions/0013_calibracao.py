# O que é: migração da fatia 11 — cria `calibracao` (relatório diário do calibrador por questão)
# e acrescenta `ix_calibracao_questao_data`. Quando ler: nunca editar depois de aplicada; mudanças
# de esquema entram em migração nova.
"""calibracao

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-19

`calibracao` é histórico (uma linha por questão por dia de execução do calibrador, nunca
sobrescrita) — ver o docstring da classe `Calibracao` em `aprovaos/dados/modelos.py`, inclusive a
nota de escopo sobre `acao` ter quatro valores aqui (`manter`/`ajustar`/`sinalizar`/`despublicar`)
em vez dos três que `docs/04-modelo-de-dados.md` §6 lista (a skill `calibracao-de-questoes`, de
fase posterior, é a fonte de verdade do contrato). Não mexe em `questao` — `despublicada_em`/
`publicada`/`dificuldade_est`/`discriminacao_est` já existiam desde a V2/V3, só ganham gravador
nesta fatia.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `calibracao`."""
    op.create_table(
        "calibracao",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("questao_id", sa.Uuid(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("dificuldade_real", sa.Float(), nullable=False),
        sa.Column("discriminacao", sa.Float(), nullable=True),
        sa.Column("n", sa.Integer(), nullable=False),
        sa.Column("acao", sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calibracao")),
        sa.ForeignKeyConstraint(
            ["questao_id"], ["questao.id"], name=op.f("fk_calibracao_questao_id_questao")
        ),
        sa.CheckConstraint(
            "acao IN ('manter','ajustar','sinalizar','despublicar')",
            name=op.f("ck_calibracao_acao"),
        ),
    )
    with op.batch_alter_table("calibracao", schema=None) as batch_op:
        batch_op.create_index("ix_calibracao_questao_data", ["questao_id", "data"], unique=False)


def downgrade() -> None:
    """Remove `calibracao`."""
    with op.batch_alter_table("calibracao", schema=None) as batch_op:
        batch_op.drop_index("ix_calibracao_questao_data")
    op.drop_table("calibracao")
