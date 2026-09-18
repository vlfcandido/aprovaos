# O que é: testes do passo 3 da V2 — o script gera o PDF da fixture, o PDF está commitado e o
# `.gitignore` não o esconde. Quando ler: ao regenerar a fixture ou mexer no `.gitignore`.
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "gerar_fixture_pdf.py"
FIXTURE_MD = RAIZ / "docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md"
FIXTURE_PDF = RAIZ / "knowledge/fixtures/editais/edital-assessor-gabinete.pdf"


def test_script_gera_pdf(tmp_path: Path) -> None:
    destino = tmp_path / "e.pdf"
    resultado = subprocess.run(
        [sys.executable, str(SCRIPT), str(FIXTURE_MD), str(destino)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert destino.read_bytes().startswith(b"%PDF-")


def test_fixture_pdf_commitada_existe() -> None:
    assert FIXTURE_PDF.read_bytes().startswith(b"%PDF-")


def test_gitignore_libera_fixtures_pdf() -> None:
    linhas = [linha.strip() for linha in (RAIZ / ".gitignore").read_text("utf-8").splitlines()]
    assert "*.pdf" in linhas
    assert "!knowledge/fixtures/**/*.pdf" in linhas
    assert linhas.index("!knowledge/fixtures/**/*.pdf") > linhas.index("*.pdf")
