# O que é: migração que normaliza a grafia de `topico.materia`, fechando pelo lado do dado o bug
# de fusão de matérias corrigido no parser. Quando ler: nunca editar depois de aplicada.
"""normaliza topico.materia

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-19

O parser preserva a grafia do edital, e editais reais escrevem a mesma matéria de formas
diferentes — o TJ-PR tem `LÍNGUA PORTUGUESA` em uma linha e `Língua Portuguesa` em outras 21, do
mesmo anexo. Antes desta migração isso virava **duas matérias** no painel, no diagnóstico e na
previsão: dois pesos, dois grupos, dois números.

A escrita passou a gravar normalizado (`dados/repositorio_edital._obter_ou_criar_topico`), e a
leitura já normalizava. Falta o passado: esta migração aplica a mesma regra às linhas existentes.

A regra é copiada aqui de propósito, em vez de importar `dominio.edital.normalizar_materia`:
migração é registro histórico e tem de continuar fazendo o que fez no dia em que rodou, mesmo
que a função do domínio mude depois.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Conectivos que ficam em minúscula fora da primeira palavra ("Noções de Informática").
_CONECTIVOS = {"de", "da", "do", "das", "dos", "e"}


def _normalizar(nome: str) -> str:
    """A mesma regra de `dominio.edital.normalizar_materia`, congelada nesta migração."""

    def capitalizar(palavra: str) -> str:
        resultado = palavra.lower()
        for indice, caractere in enumerate(resultado):
            if indice == 0 or resultado[indice - 1] in "/-":
                resultado = resultado[:indice] + caractere.upper() + resultado[indice + 1 :]
        return resultado

    palavras = nome.strip().split()
    return " ".join(
        palavra.lower() if indice > 0 and palavra.lower() in _CONECTIVOS else capitalizar(palavra)
        for indice, palavra in enumerate(palavras)
    )


def upgrade() -> None:
    """Reescreve `topico.materia` na grafia normalizada, linha a linha."""
    conexao = op.get_bind()
    linhas = conexao.execute(sa.text("SELECT id, materia FROM topico")).fetchall()
    for identificador, materia in linhas:
        normalizada = _normalizar(materia)
        if normalizada != materia:
            conexao.execute(
                sa.text("UPDATE topico SET materia = :m WHERE id = :i"),
                {"m": normalizada, "i": identificador},
            )


def downgrade() -> None:
    """Não desfaz: a grafia original de cada linha não é recuperável a partir da normalizada.

    Descer desta migração deixa `topico.materia` normalizada, que é um estado válido — só não é
    o anterior. Levantar exceção aqui obrigaria a restaurar de backup para reverter uma coisa
    que não precisa ser revertida.
    """
