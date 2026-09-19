"""Carrega, offline, o texto de súmulas do STF/STJ para o dossiê de tópico (fatia 4).

O que é: `resolver_sumulas_offline(pedidos)` — a ponte de I/O entre `dominio.dossie.PedidoSumula`
e os dicts `sumulas_texto`/`sumulas_url` que `dominio.dossie.montar_dossie` consome (a mesma
divisão de responsabilidade de `motor.ancorar.html_offline_da_norma` para normas: o `dominio`
não faz I/O, quem chama lê o arquivo/PDF e entrega string pronta). Duas fontes, com resolução
bem diferente uma da outra:

- **STJ**: um único PDF (`knowledge/fixtures/juridico/stj_sumulas_verbetes.pdf`) traz todas as
  súmulas vigentes — qualquer número pedido é resolvido, sem precisar de fixture por súmula.
- **STF**: cada súmula é uma página baixada à parte (`_PAGINAS_STF_OFFLINE`); só as chaves que já
  têm página nesta rodada resolvem — uma súmula do STF sem página baixada não é erro, vira
  lacuna em `montar_dossie` (mesma disciplina de uma norma sem fixture offline).

Nenhuma chamada acontece na importação deste módulo — a leitura do PDF/HTML só ocorre dentro de
`resolver_sumulas_offline`.

Quando ler: ao acrescentar uma súmula do STF nova a `_PAGINAS_STF_OFFLINE`, ou ao investigar por
que uma súmula pedida virou lacuna no dossiê.
"""

from pathlib import Path

import pypdfium2 as pdfium

from aprovaos.dominio.dossie import PedidoSumula
from aprovaos.dominio.erros import SumulaNaoEncontrada
from aprovaos.dominio.sumula import extrair_sumulas_stj, extrair_texto_sumula_stf

_RAIZ_DO_REPOSITORIO = Path(__file__).resolve().parents[4]
_DIR_JURIDICO = _RAIZ_DO_REPOSITORIO / "knowledge" / "fixtures" / "juridico"

_ARQUIVO_STJ = "stj_sumulas_verbetes.pdf"
_URL_STJ = (
    "https://scon.stj.jus.br/docs_internet/jurisprudencia/tematica/download/SU/Verbetes/"
    "VerbetesSTJ.pdf"
)

_PAGINAS_STF_OFFLINE: dict[str, tuple[str, str]] = {
    "stf-sumula-473": (
        "stf_sumula_473.html",
        "https://portal.stf.jus.br/jurisprudencia/sumariosumulas.asp?base=30&sumula=1602",
    ),
    "stf-sv-1": (
        "stf_sumula_vinculante_1.html",
        "https://portal.stf.jus.br/jurisprudencia/sumariosumulas.asp?base=26&sumula=1185",
    ),
    "stf-sv-11": (
        "stf_sumula_vinculante_11.html",
        "https://portal.stf.jus.br/jurisprudencia/sumariosumulas.asp?base=26&sumula=1220",
    ),
}
"""As súmulas do STF já baixadas nesta fatia — chave → `(arquivo, url)`. O id interno na URL
(`sumula=1602`, `sumula=1185`, `sumula=1220`) já foi resolvido pelo índice
(`dominio.sumula.resolver_id_interno_stf`) no momento em que a página foi baixada; uma súmula
nova do STF entra aqui como uma linha nova, decidida por quem monta a receita do dossiê — não
por varredura (mesmo espírito do catálogo de normas, `motor.fontes.planalto.CATALOGO`)."""


def _extrair_texto_pdf(caminho: Path) -> str:
    """Extrai o texto puro de todas as páginas de um PDF (I/O real — só chamado aqui)."""
    documento = pdfium.PdfDocument(str(caminho))
    return "".join(pagina.get_textpage().get_text_range() for pagina in documento)


def _resolver_stj(pedidos: list[PedidoSumula]) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve os pedidos do STJ contra o PDF único de verbetes; lê o PDF no máximo uma vez."""
    texto: dict[str, str] = {}
    url: dict[str, str] = {}
    pedidos_stj = [p for p in pedidos if p.tribunal == "stj"]
    if not pedidos_stj:
        return texto, url

    texto_pdf = _extrair_texto_pdf(_DIR_JURIDICO / _ARQUIVO_STJ)
    sumulas = extrair_sumulas_stj(texto_pdf)
    for pedido in pedidos_stj:
        if pedido.numero in sumulas:
            texto[pedido.chave] = sumulas[pedido.numero]
            url[pedido.chave] = _URL_STJ
    return texto, url


def _resolver_stf(pedidos: list[PedidoSumula]) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve os pedidos do STF contra as páginas já baixadas (`_PAGINAS_STF_OFFLINE`)."""
    texto: dict[str, str] = {}
    url: dict[str, str] = {}
    for pedido in pedidos:
        if pedido.tribunal != "stf":
            continue
        entrada = _PAGINAS_STF_OFFLINE.get(pedido.chave)
        if entrada is None:
            continue  # sem página baixada nesta rodada — vira lacuna em `montar_dossie`
        arquivo, url_pagina = entrada
        html_pagina = (_DIR_JURIDICO / arquivo).read_text(encoding="utf-8", errors="replace")
        try:
            texto[pedido.chave] = extrair_texto_sumula_stf(
                html_pagina, numero=pedido.numero, vinculante=pedido.vinculante
            )
        except SumulaNaoEncontrada:
            continue  # página não bate com o pedido — vira lacuna, nunca texto errado
        url[pedido.chave] = url_pagina
    return texto, url


def resolver_sumulas_offline(pedidos: list[PedidoSumula]) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve `sumulas_texto`/`sumulas_url` para `dominio.dossie.montar_dossie`, offline.

    Args:
        pedidos: as súmulas pedidas por uma `motor.dossie.ReceitaDossie`.

    Returns:
        `(sumulas_texto, sumulas_url)`, cada um um dict por `PedidoSumula.chave` — só com as
        chaves que resolveram; as que não resolveram (STF sem página, número inexistente no PDF
        do STJ, ou página que não bate com o pedido) simplesmente não aparecem, e viram lacuna
        declarada quando `montar_dossie` processar o pedido correspondente.
    """
    texto_stj, url_stj = _resolver_stj(pedidos)
    texto_stf, url_stf = _resolver_stf(pedidos)
    return {**texto_stj, **texto_stf}, {**url_stj, **url_stf}
