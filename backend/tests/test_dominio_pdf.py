# O que é: testes do passo 4 da V2 — validação do upload e extração de texto com pypdfium2.
# Quando ler: ao mudar limite/tipo aceito do PDF ou a normalização do texto extraído.
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Spacer

from aprovaos.dominio.erros import ArquivoInvalido, PdfSemTexto
from aprovaos.dominio.pdf import LIMITE_BYTES, contar_paginas, extrair_texto, validar_pdf

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_PDF = RAIZ / "knowledge/fixtures/editais/edital-assessor-gabinete.pdf"


def test_extrair_texto_da_fixture() -> None:
    texto = extrair_texto(FIXTURE_PDF.read_bytes())
    assert "CONTEÚDO PROGRAMÁTICO" in texto
    assert "LÍNGUA PORTUGUESA" in texto
    assert "Lei nº 14.133/2021" in texto
    assert "6.2 Distribuição" in texto
    assert "\r" not in texto


def test_extrair_texto_pdf_sem_texto(tmp_path: Path) -> None:
    destino = tmp_path / "vazio.pdf"
    SimpleDocTemplate(str(destino), pagesize=A4).build([Spacer(1, 10)])
    with pytest.raises(PdfSemTexto):
        extrair_texto(destino.read_bytes())


def test_extrair_texto_bytes_invalidos() -> None:
    with pytest.raises(ArquivoInvalido):
        extrair_texto(b"nao e pdf")


def test_validar_pdf() -> None:
    validar_pdf(b"%PDF-1.4 conteudo", "application/pdf")
    with pytest.raises(ArquivoInvalido, match="Envie um arquivo PDF"):
        validar_pdf(b"%PDF-1.4 conteudo", "image/png")
    with pytest.raises(ArquivoInvalido, match="10 MB"):
        validar_pdf(b"%PDF-" + b"x" * (LIMITE_BYTES + 1), "application/pdf")
    with pytest.raises(ArquivoInvalido):
        validar_pdf(b"x" * 20, "application/pdf")


def test_contar_paginas() -> None:
    assert contar_paginas(FIXTURE_PDF.read_bytes()) == 1
    with pytest.raises(ArquivoInvalido):
        contar_paginas(b"nao e pdf")
