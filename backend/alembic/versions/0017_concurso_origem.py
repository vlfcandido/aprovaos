# O que é: migração da P-62 — `concurso.origem` separa concurso real de fixture de teste, e o
# backfill marca o edital fictício da Fase 4 pelo hash do PDF. Quando ler: nunca editar depois de
# aplicada; mudanças de esquema entram em migração nova.
"""concurso.origem (real | fixture)

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-19

Nada no banco distinguia um `Concurso` nascido de um PDF de teste de um nascido do edital real da
aluna, e as páginas públicas das famílias C e D (`dados/repositorio_publico.py`) leem o concurso
direto — publicariam número saído de um edital que um modelo inventou, apresentado como medido
(P-62, achada na execução real da fatia 13).

A coluna nasce `'real'` para todo mundo. O backfill marca como `'fixture'` só o concurso cujo
edital aponta para o documento cujo hash é o do PDF `edital-assessor-gabinete.pdf` em
`knowledge/fixtures/editais/` — identidade exata do arquivo, não heurística de nome de
órgão, que seria a repetição da ADR-0036. O hash fica aqui, na migração, porque migração é
registro histórico; ele **não** entra
no código de produção.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: sha256 de `knowledge/fixtures/editais/edital-assessor-gabinete.pdf` (o edital fictício gerado
#: por `scripts/gerar_fixture_pdf.py` na Fase 4), que é também o nome do arquivo em
#: `data/uploads`.
_HASH_EDITAL_FICTICIO = "e7d2057d4eab1ec26a78ca8a15b7d0e8098eb9462addc30ae0376499fb384f08"


def upgrade() -> None:
    """Cria `concurso.origem` com `'real'` e marca o concurso do edital fictício."""
    with op.batch_alter_table("concurso", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("origem", sa.String(length=16), nullable=False, server_default="real")
        )
        batch_op.create_check_constraint("origem", "origem IN ('real','fixture')")
    op.execute(
        sa.text(
            "UPDATE concurso SET origem = 'fixture' WHERE id IN ("
            " SELECT e.concurso_id FROM edital e"
            " JOIN documento d ON d.id = e.documento_id"
            " WHERE d.hash = :hash)"
        ).bindparams(hash=_HASH_EDITAL_FICTICIO)
    )


def downgrade() -> None:
    """Remove `concurso.origem`."""
    with op.batch_alter_table("concurso", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_concurso_origem"), type_="check")
        batch_op.drop_column("origem")
