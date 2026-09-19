# O que é: migração do passo 1 da fundação jurídica — cria `dispositivo_legal` e `citacao`
# (modelo de dados §3), a base para ancorar justificativa de questão/aula no texto de lei.
# Quando ler: nunca editar depois de aplicada; mudanças de esquema entram em migração nova.
"""dispositivo_legal

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-19

Gerada por `alembic revision --autogenerate` e revisada à mão: `DataHoraUtc` vira
`sa.DateTime(timezone=True)` (mesmo tipo no banco, convenção das migrações 0001-0004 — o
autogenerate tentou importar `aprovaos.dados.base.DataHoraUtc` sem o import correspondente, o
que quebraria ao rodar) e `id`/`criado_em`/`atualizado_em` vêm antes das colunas de domínio,
como em `0003_questoes_e_eventos`. `dispositivo_legal.citacao_canonica` é única — recoletar o
mesmo dispositivo é `UPDATE`, nunca duplicata. `citacao.conteudo_id` não é FK (convenção
polimórfica de `reporte_erro`: `conteudo_tipo` decide a tabela).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `dispositivo_legal` e `citacao`."""
    op.create_table(
        "dispositivo_legal",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("citacao_canonica", sa.String(length=120), nullable=False),
        sa.Column("norma", sa.String(length=120), nullable=False),
        sa.Column("artigo", sa.String(length=16), nullable=False),
        sa.Column("inciso", sa.String(length=16), nullable=True),
        sa.Column("paragrafo", sa.String(length=16), nullable=True),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("vigente", sa.Boolean(), nullable=False),
        sa.Column("fonte_url", sa.String(length=500), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dispositivo_legal")),
        sa.UniqueConstraint("citacao_canonica", name=op.f("uq_dispositivo_legal_citacao_canonica")),
    )

    op.create_table(
        "citacao",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conteudo_tipo", sa.String(length=16), nullable=False),
        sa.Column("conteudo_id", sa.Uuid(), nullable=False),
        sa.Column("dispositivo_id", sa.Uuid(), nullable=False),
        sa.Column("posicao", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "conteudo_tipo IN ('questao','aula','dossie')", name=op.f("ck_citacao_conteudo_tipo")
        ),
        sa.ForeignKeyConstraint(
            ["dispositivo_id"],
            ["dispositivo_legal.id"],
            name=op.f("fk_citacao_dispositivo_id_dispositivo_legal"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_citacao")),
    )
    with op.batch_alter_table("citacao", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_citacao_dispositivo_id"), ["dispositivo_id"], unique=False
        )


def downgrade() -> None:
    """Remove `citacao` e `dispositivo_legal`, na ordem inversa das dependências."""
    with op.batch_alter_table("citacao", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_citacao_dispositivo_id"))
    op.drop_table("citacao")
    op.drop_table("dispositivo_legal")
