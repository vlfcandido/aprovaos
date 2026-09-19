"""Extrator de súmula (STF e STJ) para o dossiê de tópico (fundação jurídica, jurisprudência).

O que é: três funções puras, sem I/O, que resolvem o texto integral de uma súmula a partir do
HTML/texto já baixado — a mesma disciplina de `dominio.legislacao` aplicada a jurisprudência em
vez de lei. `resolver_id_interno_stf` resolve, no índice de súmulas do STF, o id interno que a
URL da súmula individual exige (o número da súmula **não é** esse id — achado da skill
`deep-research-topico`); `extrair_texto_sumula_stf` lê o texto integral da página de uma súmula
já baixada, conferindo que é a súmula certa antes de devolver; `extrair_sumulas_stj` lê, de uma
vez só, todas as súmulas vigentes do PDF único de verbetes do STJ (que já traz o número no
próprio texto — não precisa de índice).

Súmula cancelada ou superada nunca é devolvida como se fosse vigente: `resolver_id_interno_stf`
levanta `SumulaNaoEncontrada` para as marcadas no índice do STF; `extrair_sumulas_stj` simplesmente
não captura as marcadas `(SÚMULA CANCELADA)` no PDF do STJ (o padrão exige `"VEJA MAIS"` logo
após o número, e a marcação de cancelamento se intercala exatamente aí — ver docstring de
`extrair_sumulas_stj`).

Quando ler: antes de pedir uma súmula nova para um dossiê; ao investigar por que uma súmula
pedida virou lacuna.
"""

import html as _html_stdlib
import re

from aprovaos.dominio.erros import SumulaNaoEncontrada

_PADRAO_ESPACOS = re.compile(r"\s+")
_PADRAO_TAG = re.compile(r"<[^>]+>")


def _normalizar_texto(bruto: str) -> str:
    """Decodifica entidades HTML, troca NBSP/zero-width-space por espaço normal e colapsa."""
    texto = _html_stdlib.unescape(bruto)
    texto = texto.replace("\xa0", " ").replace("​", "")
    return _PADRAO_ESPACOS.sub(" ", texto).strip()


# --- STF: índice (id interno) ------------------------------------------------------------

_PADRAO_ITEM_INDICE_STF = re.compile(
    r'<div class="sumula-item"><a[^>]*href="sumariosumulas\.asp\?base=\d+&sumula=(?P<id>\d+)">'
    r"(?P<rotulo>.*?)</a></div>",
    re.DOTALL,
)
_PADRAO_MARCADOR = re.compile(r"<em>\(\s*(?P<marcador>.*?)\s*\)</em>", re.DOTALL)


def resolver_id_interno_stf(html_indice: str, numero: int, *, vinculante: bool) -> str:
    """Resolve, no índice de súmulas do STF, o id interno da URL de uma súmula.

    O índice (`sumariosumulas.asp?base=30` para comuns, `base=26` para vinculantes) lista cada
    súmula como um link `sumariosumulas.asp?base=<base>&sumula=<id-interno>` — esse id não é o
    número da súmula (ex.: SV 11 tem id `1220`); é preciso abrir o índice e casar pelo rótulo
    visível (`"Súmula 473"`, `"Súmula Vinculante 11"`) antes de montar a URL da súmula
    individual.

    Args:
        html_indice: HTML do índice (`stf_indice_sumulas.html` ou
            `stf_indice_sumulas_vinculantes.html`), já decodificado.
        numero: número da súmula, como publicado (sem "Súmula"/"SV").
        vinculante: `True` para procurar `"Súmula Vinculante <numero>"`; `False` para
            `"Súmula <numero>"`.

    Returns:
        O id interno (string de dígitos) a usar em `sumula=<id>` na URL da súmula individual.

    Raises:
        SumulaNaoEncontrada: o número não aparece no índice, ou aparece marcado como
            `(cancelada)`/`(superada)` — nunca devolvida como se fosse vigente.
    """
    rotulo_alvo = f"Súmula Vinculante {numero}" if vinculante else f"Súmula {numero}"
    for item in _PADRAO_ITEM_INDICE_STF.finditer(html_indice):
        bruto = item.group("rotulo")
        marcador_casado = _PADRAO_MARCADOR.search(bruto)
        rotulo = _normalizar_texto(_PADRAO_MARCADOR.sub("", bruto))
        if rotulo != rotulo_alvo:
            continue
        if marcador_casado is not None:
            marcador = _normalizar_texto(marcador_casado.group("marcador"))
            raise SumulaNaoEncontrada(
                f"{rotulo_alvo} está marcada como {marcador!r} no índice do STF — não é fonte "
                "vigente."
            )
        return item.group("id")
    raise SumulaNaoEncontrada(f"{rotulo_alvo} não aparece no índice do STF fornecido.")


# --- STF: texto integral da página individual --------------------------------------------

_PADRAO_TITULO_STF = re.compile(r'<div class="titulo">\s*(?P<rotulo>.*?)\s*</div>', re.DOTALL)
_PADRAO_TEXTO_PARCOM = re.compile(
    r'class="parCOM">\s*<(?P<tag>p|div)>(?P<corpo>.*?)</(?P=tag)>', re.DOTALL
)


def extrair_texto_sumula_stf(html_pagina: str, *, numero: int, vinculante: bool) -> str:
    """Extrai o texto integral de uma súmula do STF já baixada (comum ou vinculante).

    A página tem o rótulo (`"Súmula 473"`/`"Súmula Vinculante 11"`) no primeiro
    `<div class="titulo">` e o texto no bloco `<div class="parCOM">` seguinte — que vem como
    `<p>` nas súmulas comuns e como `<div>` nas vinculantes (as duas formas medidas nesta fatia);
    a função aceita as duas.

    Args:
        html_pagina: HTML da página individual da súmula, já decodificado.
        numero: número esperado da súmula — conferido contra o rótulo da página antes de
            devolver qualquer texto (nunca devolve o texto de uma súmula diferente da pedida).
        vinculante: `True` para exigir `"Súmula Vinculante <numero>"` no rótulo da página.

    Returns:
        O texto integral do verbete (enunciado), sem tags e com espaços normalizados.

    Raises:
        SumulaNaoEncontrada: a página não tem título reconhecível, o rótulo não bate com
            `numero`/`vinculante`, ou não há bloco `.parCOM` com texto depois do título.
    """
    rotulo_alvo = f"Súmula Vinculante {numero}" if vinculante else f"Súmula {numero}"
    titulo = _PADRAO_TITULO_STF.search(html_pagina)
    if titulo is None:
        raise SumulaNaoEncontrada(f"{rotulo_alvo}: página sem bloco de título reconhecível.")

    rotulo_pagina = _normalizar_texto(titulo.group("rotulo"))
    if rotulo_pagina != rotulo_alvo:
        raise SumulaNaoEncontrada(
            f"a página é de {rotulo_pagina!r}, não de {rotulo_alvo!r} — texto não devolvido."
        )

    texto_apos_titulo = html_pagina[titulo.end() :]
    bloco_texto = _PADRAO_TEXTO_PARCOM.search(texto_apos_titulo)
    if bloco_texto is None:
        raise SumulaNaoEncontrada(f"{rotulo_alvo}: bloco de texto ('.parCOM') não encontrado.")

    sem_tags = _PADRAO_TAG.sub(" ", bloco_texto.group("corpo"))
    return _normalizar_texto(sem_tags)


# --- STJ: PDF único de verbetes -------------------------------------------------------------

_PADRAO_CABECALHO_VERBETE_STJ = re.compile(
    r"●\s*SÚMULA\s+(?P<numero>\d+)\s*VEJA MAIS\s*(?P<bloco>.*?)(?=●|\Z)", re.DOTALL
)
"""Cada verbete vigente aparece como `"● SÚMULA <n> VEJA MAIS <texto> (<citação com 'julgado
em'>)"`. Um verbete **cancelado** intercala `"(SÚMULA CANCELADA)"` entre o número e `"VEJA
MAIS"` (ex.: `"● SÚMULA 418 (SÚMULA CANCELADA) VEJA MAIS"`, medido no PDF real) — o padrão exige
`"VEJA MAIS"` logo após o número (só espaço em branco no meio), então essa marcação sozinha já
exclui as súmulas canceladas do resultado, sem precisar reconhecer o marcador explicitamente."""

_PADRAO_CITACAO_STJ = re.compile(r"\([^()]*?julgado\s+em[^()]*?\)", re.DOTALL)
"""A citação processual que fecha o enunciado (`"(CORTE ESPECIAL, julgado em ..., DJe ...)"`,
às vezes `"(SÚMULA <n>, <órgão>, julgado em ...)"`) — sempre tem `"julgado em"` dentro dos
parênteses (medido nas 641 súmulas vigentes do PDF real). Cortar o bloco na primeira ocorrência
funciona mesmo quando: (a) a citação não repete o número da súmula (formato mais recente, ~60
verbetes — achado desta fatia: um regex anterior que exigia `"(SÚMULA <n>,"` perdia esses); (b) a
palavra "julgado" aparece antes, dentro do próprio enunciado, sem parênteses (ex.: verbete 487,
"sentenças transitadas em julgado em data anterior") — como esse trecho não está entre
parênteses, `_PADRAO_CITACAO_STJ` não casa nele; (c) o verbete tem uma nota posterior
"MODIFICAÇÃO DE TEXTO: ... REDAÇÃO ANTERIOR (decisão de ..., julgado em ...)" (verbete 111) — a
primeira citação (a vigente) é a que casa, a nota histórica depois dela nunca é alcançada porque
o texto devolvido já foi cortado antes."""


def extrair_sumulas_stj(texto_pdf: str) -> dict[int, str]:
    """Extrai todas as súmulas **vigentes** do PDF único de verbetes do STJ.

    Args:
        texto_pdf: o texto puro extraído do PDF (`VerbetesSTJ.pdf`) — extração de PDF é I/O e
            fica por conta de quem chama (`motor.fontes.sumulas_offline`); esta função só
            interpreta a string.

    Returns:
        Um dicionário `{número: texto integral}` só com verbetes vigentes (641 nesta medição) —
        súmulas marcadas `(SÚMULA CANCELADA)` no PDF nunca aparecem aqui, e a citação processual
        (órgão, data de julgamento, DJe) é removida do texto devolvido.
    """
    resultado: dict[int, str] = {}
    for cabecalho in _PADRAO_CABECALHO_VERBETE_STJ.finditer(texto_pdf):
        numero = int(cabecalho.group("numero"))
        bloco = cabecalho.group("bloco")
        citacao = _PADRAO_CITACAO_STJ.search(bloco)
        if citacao is None:
            continue  # bloco sem citação reconhecível — não declara como vigente sem prova
        resultado[numero] = _normalizar_texto(bloco[: citacao.start()])
    return resultado
