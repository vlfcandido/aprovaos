# O que é: migração da correção estrutural de 19/09/2026 (ADR-0041, fecha a P-52) — cria
# `topico_relacao`: a ponte entre tópicos equivalentes de editais diferentes (modelo de dados
# §3). Quando ler: nunca editar depois de aplicada; mudanças de esquema entram em migração nova.
"""topico_relacao

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-19

Gerada por `alembic revision --autogenerate` contra uma cópia descartável do `dev.db` e revisada
para a convenção da casa (cabeçalho de duas linhas, `id`/carimbos primeiro, tipos explícitos).
`origem` traz os três valores que `docs/04-modelo-de-dados.md` §3 já previa
(`edital`/`dossie`/`coocorrencia`, nenhum com produtor ainda) mais `equivalencia_curada`
(ADR-0041); `evidencia` é a extensão desta ADR ao mínimo do modelo de dados, mesmo padrão de
`dna_concurso`/`questao`/`aula`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `topico_relacao`."""
    op.create_table(
        "topico_relacao",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("de_id", sa.Uuid(), nullable=False),
        sa.Column("para_id", sa.Uuid(), nullable=False),
        sa.Column("peso", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("origem", sa.String(length=24), nullable=False),
        sa.Column("evidencia", sa.Text(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_topico_relacao")),
        sa.ForeignKeyConstraint(
            ["de_id"], ["topico.id"], name=op.f("fk_topico_relacao_de_id_topico")
        ),
        sa.ForeignKeyConstraint(
            ["para_id"], ["topico.id"], name=op.f("fk_topico_relacao_para_id_topico")
        ),
        sa.CheckConstraint(
            "de_id <> para_id", name=op.f("ck_topico_relacao_de_id_diferente_de_para_id")
        ),
        sa.CheckConstraint(
            "origem IN ('edital','dossie','coocorrencia','equivalencia_curada')",
            name=op.f("ck_topico_relacao_origem"),
        ),
        sa.UniqueConstraint("de_id", "para_id", "origem", name=op.f("uq_topico_relacao_de_id")),
    )
    with op.batch_alter_table("topico_relacao", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_topico_relacao_de_id"), ["de_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_topico_relacao_para_id"), ["para_id"], unique=False)


def downgrade() -> None:
    """Remove `topico_relacao`."""
    with op.batch_alter_table("topico_relacao", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_topico_relacao_para_id"))
        batch_op.drop_index(batch_op.f("ix_topico_relacao_de_id"))
    op.drop_table("topico_relacao")
