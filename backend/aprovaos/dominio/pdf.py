"""Validação do upload de edital e extração de texto com pypdfium2 — funções puras, sem disco.

O que é: `LIMITE_BYTES`, `validar_pdf(conteudo, content_type)`, `extrair_texto(conteudo)` e
`contar_paginas(conteudo)`.
Quando ler: ao mudar o que a rota `/editais/subir` aceita ou como o texto chega ao parser
(`dominio/edital.py`); a junção de linhas quebradas pelo PDF é assunto do parser, não daqui.
"""

import pypdfium2

from aprovaos.dominio.erros import ArquivoInvalido, PdfSemTexto

LIMITE_BYTES = 10 * 1024 * 1024
"""Tamanho máximo do PDF aceito (10 MB)."""

_PREFIXO_PDF = b"%PDF-"
_TIPO_PDF = "application/pdf"


def validar_pdf(conteudo: bytes, content_type: str) -> None:
    """Rejeita uploads que não sejam PDF, passem de 10 MB ou não comecem com `%PDF-`.

    Args:
        conteudo: bytes do arquivo enviado (lidos até `LIMITE_BYTES + 1`).
        content_type: tipo MIME declarado pelo navegador.

    Raises:
        ArquivoInvalido: com mensagem pt-BR pronta para o formulário.
    """
    if content_type != _TIPO_PDF:
        raise ArquivoInvalido("Envie um arquivo PDF.")
    if len(conteudo) > LIMITE_BYTES:
        raise ArquivoInvalido("O PDF passa de 10 MB. Envie um arquivo menor.")
    if not conteudo.startswith(_PREFIXO_PDF):
        raise ArquivoInvalido("O arquivo não é um PDF válido.")


def extrair_texto(conteudo: bytes) -> str:
    """Extrai o texto de todas as páginas do PDF, com quebras de linha normalizadas para LF.

    O PDFium devolve CRLF entre linhas (e pode quebrar palavras no meio quando o PDF veio de
    parágrafos justificados); aqui só se normaliza o separador — reunir linhas é papel do
    parser do conteúdo programático.

    Args:
        conteudo: bytes de um PDF já validado por `validar_pdf`.

    Returns:
        Texto das páginas na ordem, separadas por LF; sem nenhum CR.

    Raises:
        ArquivoInvalido: se o PDFium não conseguir abrir o documento (corrompido).
        PdfSemTexto: se nenhuma página tiver texto extraível.
    """
    try:
        with pypdfium2.PdfDocument(conteudo) as pdf:
            paginas = [pagina.get_textpage().get_text_range() for pagina in pdf]
    except pypdfium2.PdfiumError as erro:
        raise ArquivoInvalido("O arquivo não é um PDF válido.") from erro
    texto = "\n".join(paginas).replace("\r\n", "\n").replace("\r", "\n")
    if not texto.strip():
        raise PdfSemTexto(
            "Este PDF não tem texto extraível (parece uma imagem digitalizada). "
            "Envie a versão em texto do edital."
        )
    return texto


def contar_paginas(conteudo: bytes) -> int:
    """Conta as páginas do PDF (para `documento.metadados`).

    Args:
        conteudo: bytes de um PDF já validado por `validar_pdf`.

    Returns:
        O número de páginas.

    Raises:
        ArquivoInvalido: se o PDFium não conseguir abrir o documento.
    """
    try:
        with pypdfium2.PdfDocument(conteudo) as pdf:
            return len(pdf)
    except pypdfium2.PdfiumError as erro:
        raise ArquivoInvalido("O arquivo não é um PDF válido.") from erro
