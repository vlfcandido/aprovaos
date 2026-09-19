# O que é: migração da fatia 6 — cria `aula` (modelo de dados §3): a aula de um tópico, gerada a
# partir do dossiê e validada mecanicamente antes de publicar. Quando ler: nunca editar depois de
# aplicada; mudanças de esquema entram em migração nova.
"""aula

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-19

Mesma convenção de `dossie_topico` (migração 0006): `UniqueConstraint(topico_id, versao)` impede
duas versões iguais da aula do mesmo tópico; `dossie_id`/`dossie_versao` gravam de qual dossiê
esta aula veio (regeneração quando o dossiê muda é trabalho futuro, fatia 8). `como_a_banca_cobra`
e `lacunas_declaradas` são a extensão desta fatia ao mínimo de `docs/04-modelo-de-dados.md` §3
(mesmo padrão de `dna_concurso`/`questao`); `mnemonico` é o mnemônico opcional gerado junto com a
aula (linha 6 do PRD, §5 do plano `docs/fatias/6-trilha-e-aulas.md`).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `aula`."""
    op.create_table(
        "aula",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dossie_id", sa.Uuid(), nullable=False),
        sa.Column("dossie_versao", sa.Integer(), nullable=False),
        sa.Column("topico_id", sa.Uuid(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("texto_denso", sa.Text(), nullable=False),
        sa.Column("texto_leigo", sa.Text(), nullable=False),
        sa.Column("audio_url", sa.String(length=500), nullable=True),
        sa.Column("citacoes", sa.JSON(), nullable=False),
        sa.Column("relacionados", sa.JSON(), nullable=False),
        sa.Column("como_a_banca_cobra", sa.JSON(), nullable=False),
        sa.Column("lacunas_declaradas", sa.JSON(), nullable=False),
        sa.Column("mnemonico", sa.JSON(), nullable=True),
        sa.Column("validado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publicada", sa.Boolean(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_aula")),
        sa.ForeignKeyConstraint(
            ["dossie_id"], ["dossie_topico.id"], name=op.f("fk_aula_dossie_id_dossie_topico")
        ),
        sa.ForeignKeyConstraint(
            ["topico_id"], ["topico.id"], name=op.f("fk_aula_topico_id_topico")
        ),
        sa.UniqueConstraint("topico_id", "versao", name=op.f("uq_aula_topico_id")),
    )
    with op.batch_alter_table("aula", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_aula_topico_id"), ["topico_id"], unique=False)


def downgrade() -> None:
    """Remove `aula`."""
    with op.batch_alter_table("aula", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_aula_topico_id"))
    op.drop_table("aula")
