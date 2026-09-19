# O que é: migração da fatia 8 — cria `plano_dia` e `bloco` (plano do dia, job noturno,
# check-in). Quando ler: nunca editar depois de aplicada; mudanças de esquema entram em migração
# nova.
"""plano_dia_e_bloco

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-19

`plano_dia` é append-only por `(usuario_id, data, versao)` (a reescrita do check-in cria uma
versão nova, nunca faz `UPDATE`); `bloco` guarda o estado atual de cada bloco do dia, com o
`porque` `NOT NULL` por contrato (F3.3). `evento_estudo` ganha `bloco_id` (FK) e `energia` —
colunas que o modelo de dados §2 já nomeava desde a Fase 3, sem produtor até esta fatia criar
`bloco`. Ver os docstrings de `PlanoDia`/`Bloco`/`EventoEstudo` em `aprovaos/dados/modelos.py`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `plano_dia` e `bloco`."""
    op.create_table(
        "plano_dia",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("gerado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("energia", sa.Integer(), nullable=True),
        sa.Column("sono_h", sa.Float(), nullable=True),
        sa.Column("tempo_min", sa.Integer(), nullable=False),
        sa.Column("modo", sa.String(length=16), nullable=False),
        sa.Column("porque_geral", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plano_dia")),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"], name=op.f("fk_plano_dia_usuario_id_usuario")
        ),
        sa.CheckConstraint(
            "modo IN ('normal','descanso','semana_prova')", name=op.f("ck_plano_dia_modo")
        ),
        sa.UniqueConstraint("usuario_id", "data", "versao", name=op.f("uq_plano_dia_usuario_id")),
    )
    with op.batch_alter_table("plano_dia", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_plano_dia_usuario_id"), ["usuario_id"], unique=False)

    op.create_table(
        "bloco",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plano_dia_id", sa.Uuid(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=16), nullable=False),
        sa.Column("topico_id", sa.Uuid(), nullable=True),
        sa.Column("aula_id", sa.Uuid(), nullable=True),
        sa.Column("duracao_min", sa.Integer(), nullable=False),
        sa.Column("hora_sugerida", sa.Time(), nullable=True),
        sa.Column("porque", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("iniciado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("concluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bloco")),
        sa.ForeignKeyConstraint(
            ["plano_dia_id"], ["plano_dia.id"], name=op.f("fk_bloco_plano_dia_id_plano_dia")
        ),
        sa.ForeignKeyConstraint(
            ["topico_id"], ["topico.id"], name=op.f("fk_bloco_topico_id_topico")
        ),
        sa.ForeignKeyConstraint(["aula_id"], ["aula.id"], name=op.f("fk_bloco_aula_id_aula")),
        sa.CheckConstraint(
            "tipo IN ('aula','questoes','revisao','resumo','descanso')",
            name=op.f("ck_bloco_tipo"),
        ),
        sa.CheckConstraint(
            "status IN ('pendente','iniciado','concluido','pulado','trocado')",
            name=op.f("ck_bloco_status"),
        ),
    )
    with op.batch_alter_table("bloco", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_bloco_plano_dia_id"), ["plano_dia_id"], unique=False)

    with op.batch_alter_table("evento_estudo", schema=None) as batch_op:
        batch_op.add_column(sa.Column("bloco_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("energia", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_evento_estudo_bloco_id_bloco"), "bloco", ["bloco_id"], ["id"]
        )


def downgrade() -> None:
    """Remove as colunas de `evento_estudo`, depois `bloco` e `plano_dia`, nesta ordem (FK)."""
    with op.batch_alter_table("evento_estudo", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_evento_estudo_bloco_id_bloco"), type_="foreignkey")
        batch_op.drop_column("energia")
        batch_op.drop_column("bloco_id")

    with op.batch_alter_table("bloco", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_bloco_plano_dia_id"))
    op.drop_table("bloco")

    with op.batch_alter_table("plano_dia", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_plano_dia_usuario_id"))
    op.drop_table("plano_dia")
