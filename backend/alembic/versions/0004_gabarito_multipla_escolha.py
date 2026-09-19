# O que é: migração do passo 2 da fatia V3b — amplia o `CHECK` de `questao.gabarito`/
# `gabarito_preliminar` de C/E para A–E (múltipla escolha).
# Quando ler: nunca editar depois de aplicada; mudanças de esquema entram em migração nova.
"""gabarito_multipla_escolha

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-18

`questao.gabarito`/`gabarito_preliminar` já eram `String(1)` (cabe qualquer letra A–E) — só o
`CHECK` restringia a `'C'`/`'E'`. O SQLite não altera `CHECK` in-place; `batch_alter_table`
recria a tabela (modo batch já ligado em `alembic/env.py`, `render_as_batch=True`). O nome que se
passa a `drop_constraint` precisa de `op.f(...)` (já é o nome final, "ck_questao_gabarito") para
o modo batch não aplicar a convenção de nomes de novo em cima dele — sem isso ele tenta apagar
"ck_questao_ck_questao_gabarito" e falha; `create_check_constraint` recebe o nome curto
("gabarito"), a mesma convenção que o `CheckConstraint(name="gabarito")` do modelo usa, e a
própria convenção o resolve para o nome final de novo.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Troca os dois `CHECK` de C/E para A–E."""
    with op.batch_alter_table("questao", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_questao_gabarito"), type_="check")
        batch_op.drop_constraint(op.f("ck_questao_gabarito_preliminar"), type_="check")
        batch_op.create_check_constraint(
            "gabarito", "gabarito IS NULL OR gabarito IN ('A','B','C','D','E')"
        )
        batch_op.create_check_constraint(
            "gabarito_preliminar",
            "gabarito_preliminar IS NULL OR gabarito_preliminar IN ('A','B','C','D','E')",
        )


def downgrade() -> None:
    """Volta os dois `CHECK` para C/E — quebra se alguma linha já tiver A/B/D gravado."""
    with op.batch_alter_table("questao", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_questao_gabarito"), type_="check")
        batch_op.drop_constraint(op.f("ck_questao_gabarito_preliminar"), type_="check")
        batch_op.create_check_constraint("gabarito", "gabarito IS NULL OR gabarito IN ('C','E')")
        batch_op.create_check_constraint(
            "gabarito_preliminar",
            "gabarito_preliminar IS NULL OR gabarito_preliminar IN ('C','E')",
        )
