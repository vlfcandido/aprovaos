# O que é: migração do passo 10 da V3 — cria fonte, questao, alternativa, evento_estudo e
# reporte_erro (modelo de dados §3/§4) e acrescenta `topico_edital.grupo` (P-26).
# Quando ler: nunca editar depois de aplicada; mudanças de esquema entram em migração nova.
"""questoes_e_eventos

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-18

Gerada por `alembic revision --autogenerate` e revisada: `DataHoraUtc` vira
`sa.DateTime(timezone=True)` (mesmo tipo no banco), `id` vem primeiro e as tabelas seguem a
ordem das dependências (fonte, questao, alternativa, evento_estudo, reporte_erro). `questao`
guarda `origem`/`regra_prova` como JSON (mesmos modelos Pydantic de `dominio/questao.py`) e o
enum de `gabarito_status` nasce com cinco valores — o quinto (`sem_gabarito`) é o item sem
nenhuma entrada no gabarito. `evento_estudo` não tem `atualizado_em` (append-only) e o `CHECK`
de `tipo` já traz os dez valores do modelo de dados, para as próximas fatias não precisarem de
migração só para isso.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria as cinco tabelas de questões/eventos e acrescenta `topico_edital.grupo`."""
    op.create_table(
        "fonte",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("id_externo", sa.String(length=64), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("url_lista", sa.String(length=500), nullable=False),
        sa.Column("politica", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("ultima_varredura", sa.DateTime(timezone=True), nullable=True),
        sa.Column("proxima", sa.DateTime(timezone=True), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('ativa','vetada','pendente_mapeamento')", name=op.f("ck_fonte_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fonte")),
        sa.UniqueConstraint("id_externo", name=op.f("uq_fonte_id_externo")),
    )

    op.create_table(
        "questao",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("adapter", sa.String(length=32), nullable=False),
        sa.Column("banca", sa.String(length=64), nullable=False),
        sa.Column("tipo_item", sa.String(length=32), nullable=False),
        sa.Column("comando", sa.Text(), nullable=True),
        sa.Column("texto_apoio", sa.Text(), nullable=True),
        sa.Column("texto_apoio_itens", sa.JSON(), nullable=False),
        sa.Column("enunciado", sa.Text(), nullable=False),
        sa.Column("gabarito_preliminar", sa.String(length=1), nullable=True),
        sa.Column("gabarito", sa.String(length=1), nullable=True),
        sa.Column("gabarito_status", sa.String(length=16), nullable=False),
        sa.Column("publicavel", sa.Boolean(), nullable=False),
        sa.Column("publicada", sa.Boolean(), nullable=False),
        sa.Column("despublicada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_nao_publicavel", sa.Text(), nullable=True),
        sa.Column("regra_prova", sa.JSON(), nullable=False),
        sa.Column("topico_id", sa.Uuid(), nullable=True),
        sa.Column("topico_confianca", sa.String(length=8), nullable=False),
        sa.Column("topico_evidencia", sa.Text(), nullable=False),
        sa.Column("origem", sa.JSON(), nullable=True),
        sa.Column("inedita", sa.Boolean(), nullable=False),
        sa.Column("documento_id", sa.Uuid(), nullable=True),
        sa.Column("hash_dedup", sa.String(length=40), nullable=False),
        sa.Column("dificuldade_est", sa.Float(), nullable=True),
        sa.Column("discriminacao_est", sa.Float(), nullable=True),
        sa.Column("validada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validador_versao", sa.String(length=64), nullable=True),
        sa.Column("justificativa_certo", sa.Text(), nullable=True),
        sa.Column("justificativa_errado", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "gabarito IS NULL OR gabarito IN ('C','E')", name=op.f("ck_questao_gabarito")
        ),
        sa.CheckConstraint(
            "gabarito_preliminar IS NULL OR gabarito_preliminar IN ('C','E')",
            name=op.f("ck_questao_gabarito_preliminar"),
        ),
        sa.CheckConstraint(
            "gabarito_status IN ('definitivo','preliminar','anulado','alterado','sem_gabarito')",
            name=op.f("ck_questao_gabarito_status"),
        ),
        sa.CheckConstraint(
            "topico_confianca IN ('alta','media','baixa')",
            name=op.f("ck_questao_topico_confianca"),
        ),
        sa.ForeignKeyConstraint(
            ["documento_id"], ["documento.id"], name=op.f("fk_questao_documento_id_documento")
        ),
        sa.ForeignKeyConstraint(
            ["topico_id"], ["topico.id"], name=op.f("fk_questao_topico_id_topico")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questao")),
        sa.UniqueConstraint("hash_dedup", name=op.f("uq_questao_hash_dedup")),
    )

    op.create_table(
        "alternativa",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("questao_id", sa.Uuid(), nullable=False),
        sa.Column("letra", sa.String(length=1), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("correta", sa.Boolean(), nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["questao_id"], ["questao.id"], name=op.f("fk_alternativa_questao_id_questao")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alternativa")),
        sa.UniqueConstraint("questao_id", "letra", name=op.f("uq_alternativa_questao_id")),
    )
    with op.batch_alter_table("alternativa", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_alternativa_questao_id"), ["questao_id"], unique=False)

    op.create_table(
        "evento_estudo",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("ocorrido_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tipo", sa.String(length=32), nullable=False),
        sa.Column("questao_id", sa.Uuid(), nullable=True),
        sa.Column("acertou", sa.Boolean(), nullable=True),
        sa.Column("resposta", sa.String(length=8), nullable=True),
        sa.Column("tempo_ms", sa.Integer(), nullable=True),
        sa.Column("confianca_declarada", sa.String(length=8), nullable=True),
        sa.CheckConstraint(
            "confianca_declarada IS NULL OR confianca_declarada IN ('certeza','duvida')",
            name=op.f("ck_evento_estudo_confianca_declarada"),
        ),
        sa.CheckConstraint(
            "tipo IN ("
            "'resposta','checkin','bloco_iniciado','bloco_concluido','bloco_pulado',"
            "'discordou','distracao','revisao_cartao','aula_lida','resumo_aberto','reporte'"
            ")",
            name=op.f("ck_evento_estudo_tipo"),
        ),
        sa.ForeignKeyConstraint(
            ["questao_id"], ["questao.id"], name=op.f("fk_evento_estudo_questao_id_questao")
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"], name=op.f("fk_evento_estudo_usuario_id_usuario")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evento_estudo")),
    )
    with op.batch_alter_table("evento_estudo", schema=None) as batch_op:
        batch_op.create_index(
            "ix_evento_estudo_questao_ocorrido", ["questao_id", "ocorrido_em"], unique=False
        )
        batch_op.create_index(
            "ix_evento_estudo_usuario_ocorrido", ["usuario_id", "ocorrido_em"], unique=False
        )

    op.create_table(
        "reporte_erro",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("conteudo_tipo", sa.String(length=16), nullable=False),
        sa.Column("conteudo_id", sa.Uuid(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("resolvido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "conteudo_tipo IN ('aula','questao','dossie')",
            name=op.f("ck_reporte_erro_conteudo_tipo"),
        ),
        sa.CheckConstraint(
            "status IN ('aberto','analise','corrigido','improcedente')",
            name=op.f("ck_reporte_erro_status"),
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"], name=op.f("fk_reporte_erro_usuario_id_usuario")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reporte_erro")),
    )
    with op.batch_alter_table("reporte_erro", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_reporte_erro_usuario_id"), ["usuario_id"], unique=False
        )

    with op.batch_alter_table("topico_edital", schema=None) as batch_op:
        batch_op.add_column(sa.Column("grupo", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Remove as cinco tabelas, na ordem inversa das dependências, e `topico_edital.grupo`."""
    with op.batch_alter_table("topico_edital", schema=None) as batch_op:
        batch_op.drop_column("grupo")

    with op.batch_alter_table("reporte_erro", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_reporte_erro_usuario_id"))
    op.drop_table("reporte_erro")

    with op.batch_alter_table("evento_estudo", schema=None) as batch_op:
        batch_op.drop_index("ix_evento_estudo_usuario_ocorrido")
        batch_op.drop_index("ix_evento_estudo_questao_ocorrido")
    op.drop_table("evento_estudo")

    with op.batch_alter_table("alternativa", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_alternativa_questao_id"))
    op.drop_table("alternativa")

    op.drop_table("questao")
    op.drop_table("fonte")
