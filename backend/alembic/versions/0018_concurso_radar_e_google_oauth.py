# O que é: migração da fatia 1b — cria `concurso_radar` (catálogo global da Cebraspe, F1.1) e
# prepara `usuario` para o Google OAuth (RF-20, Ruling 42). Quando ler: nunca editar depois de
# aplicada; mudanças de esquema entram em migração nova.
"""concurso_radar_e_google_oauth

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-19

`concurso_radar` espelha `dominio.radar.ConcursoDoRadar` — ver o docstring da classe
`ConcursoRadar` em `aprovaos/dados/modelos.py` para o porquê de cada coluna (em especial
`primeiro_visto_em`/`ultimo_visto_em`, que substituem `Carimbos`, e `bruto`, a última leitura
crua para auditoria). `usuario.senha_hash` vira opcional e `usuario.google_sub` nasce (`UNIQUE`,
nullable) para a conta que só entra por Google não ter senha nenhuma — ver o docstring da classe
`Usuario`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `concurso_radar` e prepara `usuario` para contas só-Google."""
    op.create_table(
        "concurso_radar",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fonte_id", sa.Uuid(), nullable=False),
        sa.Column("evento_url", sa.String(length=255), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("ano", sa.Integer(), nullable=True),
        sa.Column("fase", sa.String(length=24), nullable=False),
        sa.Column("uf", sa.String(length=2), nullable=True),
        sa.Column("vagas", sa.Integer(), nullable=True),
        sa.Column("salario_max_brl", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("periodo_inscricao_texto", sa.Text(), nullable=True),
        sa.Column("inscricao_inicio", sa.Date(), nullable=True),
        sa.Column("inscricao_fim", sa.Date(), nullable=True),
        sa.Column("lacunas", sa.JSON(), nullable=False),
        sa.Column("url_evento", sa.String(length=500), nullable=False),
        sa.Column("primeiro_visto_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ultimo_visto_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bruto", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "fase IN ('novos','inscricoes_abertas','em_andamento','encerrado')",
            name=op.f("ck_concurso_radar_fase"),
        ),
        sa.ForeignKeyConstraint(
            ["fonte_id"], ["fonte.id"], name=op.f("fk_concurso_radar_fonte_id_fonte")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_concurso_radar")),
        sa.UniqueConstraint("fonte_id", "evento_url", name=op.f("uq_concurso_radar_fonte_id")),
    )
    with op.batch_alter_table("concurso_radar", schema=None) as batch_op:
        batch_op.create_index("ix_concurso_radar_fonte_id", ["fonte_id"], unique=False)

    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.add_column(sa.Column("google_sub", sa.String(length=255), nullable=True))
        batch_op.alter_column("senha_hash", existing_type=sa.String(length=255), nullable=True)
        batch_op.create_unique_constraint(op.f("uq_usuario_google_sub"), ["google_sub"])


def downgrade() -> None:
    """Remove `concurso_radar` e desfaz a preparação de `usuario` para Google."""
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("uq_usuario_google_sub"), type_="unique")
        batch_op.alter_column("senha_hash", existing_type=sa.String(length=255), nullable=False)
        batch_op.drop_column("google_sub")

    with op.batch_alter_table("concurso_radar", schema=None) as batch_op:
        batch_op.drop_index("ix_concurso_radar_fonte_id")
    op.drop_table("concurso_radar")
