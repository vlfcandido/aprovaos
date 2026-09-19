# O que é: migração do passo 3 da fundação jurídica — cria `dossie_topico` (modelo de dados
# §3), o dossiê versionado que liga um tópico a dispositivos legais com trecho e URL.
# Quando ler: nunca editar depois de aplicada; mudanças de esquema entram em migração nova.
"""dossie_topico

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-19

Mesma convenção das migrações 0003/0005: `DataHoraUtc` vira `sa.DateTime(timezone=True)`;
`id`/`criado_em`/`atualizado_em` vêm antes das colunas de domínio. `UniqueConstraint(topico_id,
versao)` impede duas versões iguais do mesmo tópico; `substituido_por` é FK para a própria
tabela (auto-referência), nullable — só preenchida quando uma versão nova substitui esta.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `dossie_topico`."""
    op.create_table(
        "dossie_topico",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("topico_id", sa.Uuid(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("gerado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("conteudo", sa.Text(), nullable=False),
        sa.Column("fontes", sa.JSON(), nullable=False),
        sa.Column("bibliografia", sa.JSON(), nullable=False),
        sa.Column("log_buscas", sa.JSON(), nullable=False),
        sa.Column("validado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("substituido_por", sa.Uuid(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dossie_topico")),
        sa.ForeignKeyConstraint(
            ["topico_id"], ["topico.id"], name=op.f("fk_dossie_topico_topico_id_topico")
        ),
        sa.ForeignKeyConstraint(
            ["substituido_por"],
            ["dossie_topico.id"],
            name=op.f("fk_dossie_topico_substituido_por_dossie_topico"),
        ),
        sa.UniqueConstraint("topico_id", "versao", name=op.f("uq_dossie_topico_topico_id")),
    )
    with op.batch_alter_table("dossie_topico", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_dossie_topico_topico_id"), ["topico_id"], unique=False)


def downgrade() -> None:
    """Remove `dossie_topico`."""
    with op.batch_alter_table("dossie_topico", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_dossie_topico_topico_id"))
    op.drop_table("dossie_topico")
