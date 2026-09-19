# O que é: migração da fatia 7 — acrescenta `usuario.consentimento_dados_rotina*` (LGPD, R-01) e
# cria `perfil_estudo` (rotina + concurso principal, P-23). Quando ler: nunca editar depois de
# aplicada; mudanças de esquema entram em migração nova.
"""perfil_estudo

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-19

`usuario.consentimento_dados_rotina`/`_em`/`_versao` são as três colunas para o campo lógico único
que `docs/04-modelo-de-dados.md` §2 nomeia ("bool, data, versão do texto") — ver o docstring da
classe `Usuario`. `perfil_estudo` é append-only por `versao` (sem `atualizado_em`, mesmo motivo de
`evento_estudo` não ter — ver o docstring da classe `PerfilEstudo`).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Acrescenta o consentimento de rotina ao `usuario` e cria `perfil_estudo`."""
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "consentimento_dados_rotina",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column("consentimento_dados_rotina_em", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("consentimento_dados_rotina_versao", sa.String(length=16), nullable=True)
        )

    op.create_table(
        "perfil_estudo",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("horas_por_dia_semana", sa.JSON(), nullable=False),
        sa.Column("horario_preferido", sa.String(length=16), nullable=False),
        sa.Column("energia_tipica", sa.String(length=8), nullable=False),
        sa.Column("data_alvo", sa.Date(), nullable=True),
        sa.Column("concurso_principal_id", sa.Uuid(), nullable=True),
        sa.Column("concursos_acompanhados", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_perfil_estudo")),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"], name=op.f("fk_perfil_estudo_usuario_id_usuario")
        ),
        sa.ForeignKeyConstraint(
            ["concurso_principal_id"],
            ["concurso.id"],
            name=op.f("fk_perfil_estudo_concurso_principal_id_concurso"),
        ),
        sa.CheckConstraint(
            "energia_tipica IN ('alta','media','baixa')",
            name=op.f("ck_perfil_estudo_energia_tipica"),
        ),
        sa.UniqueConstraint("usuario_id", "versao", name=op.f("uq_perfil_estudo_usuario_id")),
    )
    with op.batch_alter_table("perfil_estudo", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_perfil_estudo_usuario_id"), ["usuario_id"], unique=False
        )


def downgrade() -> None:
    """Remove `perfil_estudo` e o consentimento de rotina do `usuario`."""
    with op.batch_alter_table("perfil_estudo", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_perfil_estudo_usuario_id"))
    op.drop_table("perfil_estudo")

    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.drop_column("consentimento_dados_rotina_versao")
        batch_op.drop_column("consentimento_dados_rotina_em")
        batch_op.drop_column("consentimento_dados_rotina")
