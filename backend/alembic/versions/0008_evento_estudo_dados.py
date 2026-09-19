# O que é: migração da V5 — acrescenta `evento_estudo.dados` (JSON, nullable).
# Quando ler: nunca editar depois de aplicada; mudanças de esquema entram em migração nova.
"""evento_estudo_dados

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-19

`dados` é o campo que `docs/04-modelo-de-dados.md` §2 já nomeava para `evento_estudo` desde a
Fase 3 e nenhuma fatia (V1-V4) tinha precisado criar. A V5 (fio da memória) o usa para marcar,
sem coluna nova, que uma resposta faz parte do bloco de um tópico (`bloco_topico_id`) e, quando é
um item intercalado, o motivo já formatado (`fio_motivo`) e o tópico de origem
(`fio_origem_topico_id`) — ver `docs/fatias/V5-fio-da-memoria.md` §4.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Acrescenta `evento_estudo.dados` (JSON, nullable)."""
    with op.batch_alter_table("evento_estudo", schema=None) as batch_op:
        batch_op.add_column(sa.Column("dados", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove `evento_estudo.dados`."""
    with op.batch_alter_table("evento_estudo", schema=None) as batch_op:
        batch_op.drop_column("dados")
