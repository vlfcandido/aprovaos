"""Gera o PDF da fixture de edital a partir do `.md` de evidências, com reportlab (Platypus).

O que é: script reproduzível (`uv run python ../scripts/gerar_fixture_pdf.py <origem.md>
<destino.pdf>`, de `backend/`) que descarta o cabeçalho do fixture (linhas `# ` e `> `) e
transforma cada linha não vazia num `Paragraph`; a quebra de linha do Paragraph produz o caso
"item quebrado em duas linhas" que o parser da V2 precisa tratar. Quando ler: ao regenerar
`knowledge/fixtures/editais/edital-assessor-gabinete.pdf` ou criar outra fixture de edital.
"""

import sys
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate

PREFIXOS_DESCARTADOS = ("# ", "> ")


def linhas_do_edital(texto: str) -> list[str]:
    """Filtra as linhas do `.md` que entram no PDF.

    Args:
        texto: conteúdo do arquivo de fixture em Markdown.

    Returns:
        Linhas não vazias, sem as de cabeçalho (`# ` título e `> ` "o que é / quando ler").
    """
    return [
        linha.strip()
        for linha in texto.splitlines()
        if linha.strip() and not linha.startswith(PREFIXOS_DESCARTADOS)
    ]


def gerar_pdf(origem: Path, destino: Path) -> None:
    """Escreve em `destino` um PDF A4 com um parágrafo por linha útil de `origem`.

    Args:
        origem: caminho do `.md` da fixture.
        destino: caminho do PDF a criar (a pasta é criada se não existir).
    """
    estilo = getSampleStyleSheet()["Normal"]
    linhas = linhas_do_edital(origem.read_text("utf-8"))
    paragrafos = [Paragraph(escape(linha), estilo) for linha in linhas]
    destino.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(destino), pagesize=A4).build(paragrafos)


def main(argv: list[str]) -> int:
    """Ponto de entrada: `gerar_fixture_pdf.py <origem.md> <destino.pdf>`.

    Args:
        argv: argumentos da linha de comando, sem o nome do script.

    Returns:
        0 em sucesso; 2 se os argumentos estiverem errados.
    """
    if len(argv) != 2:
        print("uso: gerar_fixture_pdf.py <origem.md> <destino.pdf>", file=sys.stderr)
        return 2
    gerar_pdf(Path(argv[0]), Path(argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
