# O que é: migração da V4 — cria `cartao` (modelo de dados §2, F4.3) e acrescenta
# `evento_estudo.cartao_id` para o tipo `revisao_cartao`.
# Quando ler: nunca editar depois de aplicada; mudanças de esquema entram em migração nova.
"""cartao

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-19

`cartao` guarda o estado do `fsrs.Card` (`Card` desta versão da lib não tem `reps`/`lapses` —
adendo à ADR-0022 em `docs/DECISOES.md`, detalhado em `docs/fatias/V4-revisao-espacada.md` §2):
os seis campos do modelo de dados (`stability, difficulty, due, reps, lapses, last_review`) mais
`estado_fsrs`/`passo_fsrs`, sem os quais reconstruir o `Card` perde a fase de aprendizado e
recalcula um `due` errado. `UniqueConstraint(usuario_id, questao_id)` é o que impede um segundo
cartão para a mesma questão do mesmo usuário. `evento_estudo.cartao_id` só entra depois de
`cartao` existir — segue a mesma convenção de `DataHoraUtc` → `sa.DateTime(timezone=True)` das
migrações 0003/0005/0006.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `cartao` e acrescenta `evento_estudo.cartao_id`."""
    op.create_table(
        "cartao",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("questao_id", sa.Uuid(), nullable=True),
        sa.Column("topico_id", sa.Uuid(), nullable=False),
        sa.Column("frente", sa.Text(), nullable=False),
        sa.Column("verso", sa.Text(), nullable=False),
        sa.Column("mnemonico_id", sa.Uuid(), nullable=True),
        sa.Column("origem", sa.String(length=16), nullable=False),
        sa.Column("stability", sa.Float(), nullable=True),
        sa.Column("difficulty", sa.Float(), nullable=True),
        sa.Column("due", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column("lapses", sa.Integer(), nullable=False),
        sa.Column("last_review", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estado_fsrs", sa.Integer(), nullable=False),
        sa.Column("passo_fsrs", sa.Integer(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("origem IN ('auto_erro','manual')", name=op.f("ck_cartao_origem")),
        sa.ForeignKeyConstraint(
            ["questao_id"], ["questao.id"], name=op.f("fk_cartao_questao_id_questao")
        ),
        sa.ForeignKeyConstraint(
            ["topico_id"], ["topico.id"], name=op.f("fk_cartao_topico_id_topico")
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"], name=op.f("fk_cartao_usuario_id_usuario")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cartao")),
        sa.UniqueConstraint("usuario_id", "questao_id", name=op.f("uq_cartao_usuario_id")),
    )
    with op.batch_alter_table("cartao", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_cartao_usuario_id"), ["usuario_id"], unique=False)
        batch_op.create_index("ix_cartao_usuario_due", ["usuario_id", "due"], unique=False)

    with op.batch_alter_table("evento_estudo", schema=None) as batch_op:
        batch_op.add_column(sa.Column("cartao_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_evento_estudo_cartao_id_cartao"), "cartao", ["cartao_id"], ["id"]
        )


def downgrade() -> None:
    """Remove `evento_estudo.cartao_id` e a tabela `cartao`."""
    with op.batch_alter_table("evento_estudo", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_evento_estudo_cartao_id_cartao"), type_="foreignkey"
        )
        batch_op.drop_column("cartao_id")

    with op.batch_alter_table("cartao", schema=None) as batch_op:
        batch_op.drop_index("ix_cartao_usuario_due")
        batch_op.drop_index(batch_op.f("ix_cartao_usuario_id"))
    op.drop_table("cartao")
