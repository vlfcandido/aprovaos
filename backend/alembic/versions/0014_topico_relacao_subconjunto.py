# O que é: migração da revisão independente de 19/09/2026 (I1) — amplia o `CHECK` de
# `topico_relacao.origem` para aceitar `subconjunto_curado` (cobertura parcial, peso < 1),
# separado de `equivalencia_curada` (plena), e corrige o único par já gravado com a origem
# errada (recursos, Cascavel × TJ-PR). Quando ler: nunca editar depois de aplicada; mudanças de
# esquema entram em migração nova.
"""topico_relacao_subconjunto

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-19

Mesma técnica de `0004_gabarito_multipla_escolha.py` para o `CHECK` (SQLite não altera in-place;
`batch_alter_table` recria a tabela). Além disso, corrige o dado: o par
`dir-pro-civ-05-recursos-apelacao <-> noc-dir-pro-civ-07-recursos`, gravado pela ADR-0041
original como `equivalencia_curada`/peso 1 apesar de a própria evidência já dizer "a cobertura
do dossiê é parcial", passa a `subconjunto_curado`/peso 0,5. A correção mira pela evidência
antiga (frase única, "agravo de instrumento" não aparece em nenhum outro par curado), não pelo
par de tópicos — mais simples que reabrir a junção com `topico` e indiferente à direção
`de_id`/`para_id` gravada.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TOPICO_RELACAO = sa.table(
    "topico_relacao",
    sa.column("origem", sa.String),
    sa.column("peso", sa.Numeric),
    sa.column("evidencia", sa.Text),
)

_EVIDENCIA_ANTIGA_TRECHO = "agravo de instrumento"

_EVIDENCIA_NOVA = (
    "ambos citam literalmente 'recursos' (edital Cascavel/Unioeste §5, que detalha apelação, "
    "agravo de instrumento e embargos de declaração — as três modalidades mais comuns do CPC), "
    "mas isso é um subconjunto do item genérico 'Dos recursos' do edital TJ-PR/AOCP, Noções de "
    "Direito Processual Civil item 7 — a cobertura do dossiê é parcial em relação ao item do "
    "TJ-PR, não incorreta, e a tela avisa isso"
)

_EVIDENCIA_ORIGINAL = (
    "ambos citam literalmente 'recursos' (edital Cascavel/Unioeste §5, que detalha apelação, "
    "agravo de instrumento e embargos de declaração — as três modalidades mais comuns do CPC, "
    "um subconjunto honesto do item genérico 'Dos recursos' do edital TJ-PR/AOCP, Noções de "
    "Direito Processual Civil item 7; a cobertura do dossiê é parcial em relação ao item do "
    "TJ-PR, não incorreta)"
)


def upgrade() -> None:
    """Acrescenta `subconjunto_curado` ao `CHECK` e corrige o par de recursos para essa origem."""
    with op.batch_alter_table("topico_relacao", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_topico_relacao_origem"), type_="check")
        batch_op.create_check_constraint(
            "origem",
            "origem IN ('edital','dossie','coocorrencia','equivalencia_curada',"
            "'subconjunto_curado')",
        )
    op.execute(
        sa.update(_TOPICO_RELACAO)
        .where(_TOPICO_RELACAO.c.origem == "equivalencia_curada")
        .where(_TOPICO_RELACAO.c.evidencia.like(f"%{_EVIDENCIA_ANTIGA_TRECHO}%"))
        .values(origem="subconjunto_curado", peso=0.5, evidencia=_EVIDENCIA_NOVA)
    )


def downgrade() -> None:
    """Devolve o par de recursos a `equivalencia_curada`/peso 1 e volta o `CHECK` anterior."""
    op.execute(
        sa.update(_TOPICO_RELACAO)
        .where(_TOPICO_RELACAO.c.origem == "subconjunto_curado")
        .where(_TOPICO_RELACAO.c.evidencia.like(f"%{_EVIDENCIA_ANTIGA_TRECHO}%"))
        .values(origem="equivalencia_curada", peso=1, evidencia=_EVIDENCIA_ORIGINAL)
    )
    with op.batch_alter_table("topico_relacao", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_topico_relacao_origem"), type_="check")
        batch_op.create_check_constraint(
            "origem", "origem IN ('edital','dossie','coocorrencia','equivalencia_curada')"
        )
