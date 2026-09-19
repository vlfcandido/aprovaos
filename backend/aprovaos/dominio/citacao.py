"""Extrator de referência legal no texto de uma questão (fundação jurídica, passo 2).

O que é: `extrair_citacoes(texto)`, função pura que reconhece, no texto de uma questão (enunciado
+ comando + texto de apoio, concatenados por quem chama), referências a um dispositivo de norma
— `"art. 37 da CF"`, `"art. 37, caput, da Constituição Federal"`, `"Lei nº 14.133/2021"`, `"art.
6º da Lei 14.133/2021"`, `"§ 1º do art. 37 da CF"`, `"inciso II do art. 37 da CF"` — e devolve
cada uma normalizada (`ReferenciaLegal`). Não abre rede, não conhece banco, não sabe o que é
`dispositivo_legal`/`citacao` — só interpreta a string.

**A regra de ouro (ADR-0036)**: a citação tem de estar no texto, não ser deduzida do assunto. Uma
menção a "art. 37" sem nenhuma norma junto (`"§ 1º do art. 37"`, sozinho) é ambígua — poderia ser
CF, poderia ser outra lei com artigo 37 — e **não vira citação**; isso é resultado válido desta
função, não uma falha dela. O mesmo vale para o acrônimo `CF`: só conta em maiúsculas exatas (a
abreviação acadêmica `"cf."` — de "confira" — é sempre minúscula e nunca é confundida com a
Constituição Federal por este motivo).

Uma referência à norma sozinha, sem artigo (`"Lei nº 14.133/2021"`), também é uma citação válida
— só não é suficiente para apontar um dispositivo específico (`artigo` sai `None`); quem persiste
decide o que fazer com isso (`motor/ancorar_citacoes.py`).

Quando ler: antes de mudar a gramática reconhecida (nova forma de citar artigo/norma); ao
investigar por que uma questão com citação "óbvia" não gerou `ReferenciaLegal`.
"""

import re

from pydantic import BaseModel

_NUMERO_ORDINAL = r"\d+\s*(?:\.\s*)?[º°]?\.?"
"""Um número de artigo/parágrafo como a banca escreve: `"37"`, `"6º"`, `"1.º"`, `"10."`."""

_ROMANO = r"[IVXLCDM]+"


def _normalizar_numero(bruto: str) -> str:
    """`"6º"` / `"1.º"` / `"10."` → `"6"` / `"1"` / `"10"` (só os dígitos)."""
    return re.sub(r"[^\d]", "", bruto)


_ARTIGO_NUCLEO = re.compile(rf"art(?:igo)?\.?\s*(?P<numero>{_NUMERO_ORDINAL})", re.IGNORECASE)

_QUALIFICADOR_SUFIXO = re.compile(
    r"\s*,\s*(?:caput"
    rf"|inciso\s+(?P<inciso>{_ROMANO})"
    rf"|§\s*(?P<paragrafo>{_NUMERO_ORDINAL})"
    rf"|par[áa]grafo\s+(?:único|(?P<paragrafo2>{_NUMERO_ORDINAL})))"
    r"\s*,?",
    re.IGNORECASE,
)

_QUALIFICADOR_PREFIXO = re.compile(
    r"(?:caput"
    rf"|inciso\s+(?P<inciso>{_ROMANO})"
    rf"|§\s*(?P<paragrafo>{_NUMERO_ORDINAL})"
    rf"|par[áa]grafo\s+(?:único|(?P<paragrafo2>{_NUMERO_ORDINAL})))"
    r"\s+d[oa]\s*$",
    re.IGNORECASE,
)

_CONECTOR = re.compile(r"\s*d[oa]\s+", re.IGNORECASE)

# Cada norma reconhecida — checada nesta ordem porque "Lei Complementar" também começa com
# "Lei " (a alternativa mais específica precisa vir primeiro). Sem `re.IGNORECASE`: "Lei",
# "Constituição Federal" e "CLT" são sempre escritos em maiúscula própria pela banca; o acrônimo
# "CF" em maiúsculas exatas é o que distingue da abreviação acadêmica minúscula "cf." (de
# "confira"), que nunca é a Constituição Federal.
_INDICADOR_NUMERO = r"(?:n[º°o.]*\s*)?"
"""O `"nº"`/`"n.º"`/`"n°"` opcional antes do número da lei — opcional porque a banca às vezes
escreve só `"Lei 14.133/2021"`, sem indicador nenhum antes do número."""

_NORMA = re.compile(
    rf"Lei\s+Complementar\s+{_INDICADOR_NUMERO}(?P<lc_numero>[\d.]+)\s*/\s*(?P<lc_ano>\d{{4}})"
    rf"|Lei\s+{_INDICADOR_NUMERO}(?P<lei_numero>[\d.]+)\s*/\s*(?P<lei_ano>\d{{4}})"
    r"|Constitui[cç][ãa]o Federal(?:\s+de\s+1988)?"
    r"|CF\s*/\s*(?:19)?88"
    r"|CF\b"
    r"|CLT\b"
)


class ReferenciaLegal(BaseModel):
    """Uma referência normativa reconhecida no texto de uma questão, já normalizada.

    Attributes:
        norma: id estável da norma citada. Para as normas do catálogo de fontes
            (`motor.fontes.planalto.CATALOGO`), o mesmo id de lá (`"cf-1988"`,
            `"lei-14133-2021"`) — para as demais, um slug igualmente estável (`"lei-8429-1992"`,
            `"lei-complementar-109-2001"`, `"clt"`), nunca o texto cru da citação.
        artigo: número do artigo, sem `"art."`/ordinal (ex.: `"37"`, `"6"`); `None` quando o
            trecho só cita a norma, sem apontar um artigo (ex.: `"Lei nº 14.133/2021"`).
        inciso: identificador do inciso, em algarismos romanos (ex.: `"II"`); `None` quando a
            citação não desce a esse nível.
        paragrafo: número do parágrafo, sem `"§"`/ordinal (ex.: `"1"`); `None` quando a citação é
            do caput (implícito ou explícito) ou não desce a esse nível.
        trecho: o texto original (como apareceu na questão) que gerou esta referência —
            preservado para auditoria; nunca reconstruído.
    """

    norma: str
    artigo: str | None
    inciso: str | None
    paragrafo: str | None
    trecho: str


def _norma_id(casamento: re.Match[str]) -> str:
    """Resolve o id estável da norma a partir do `re.Match` de `_NORMA`."""
    if casamento.group("lc_numero"):
        numero = casamento.group("lc_numero").replace(".", "")
        return f"lei-complementar-{numero}-{casamento.group('lc_ano')}"
    if casamento.group("lei_numero"):
        numero = casamento.group("lei_numero").replace(".", "")
        return f"lei-{numero}-{casamento.group('lei_ano')}"
    if casamento.group(0).upper().startswith("CLT"):
        return "clt"
    return "cf-1988"


def _partes_do_qualificador(casamento: re.Match[str] | None) -> tuple[str | None, str | None]:
    """`(inciso, paragrafo)` a partir de um `_QUALIFICADOR_PREFIXO`/`_QUALIFICADOR_SUFIXO`."""
    if casamento is None:
        return None, None
    grupos = casamento.groupdict()
    inciso = grupos.get("inciso")
    paragrafo = grupos.get("paragrafo") or grupos.get("paragrafo2")
    return inciso, _normalizar_numero(paragrafo) if paragrafo else None


def _tentar_sufixo(texto: str, pos: int) -> tuple[int, str | None, str | None, str] | None:
    """Casa `[qualificador ,] d[oa] <norma>` logo após o número do artigo.

    Args:
        texto: o texto completo sendo varrido.
        pos: posição logo após o número do artigo já casado.

    Returns:
        `(fim, inciso, paragrafo, norma_id)` quando há conector + norma reconhecida; `None`
        quando não há norma alguma anexada (a citação fica ambígua — ver docstring do módulo).
    """
    qualificador = _QUALIFICADOR_SUFIXO.match(texto, pos)
    pos_apos_qualificador = qualificador.end() if qualificador else pos
    conector = _CONECTOR.match(texto, pos_apos_qualificador)
    if conector is None:
        return None
    norma = _NORMA.match(texto, conector.end())
    if norma is None:
        return None
    inciso, paragrafo = _partes_do_qualificador(qualificador)
    return norma.end(), inciso, paragrafo, _norma_id(norma)


def extrair_citacoes(texto: str) -> list[ReferenciaLegal]:
    """Acha, em `texto`, todas as referências a dispositivo/norma reconhecíveis sem adivinhar.

    Dois tipos de referência saem daqui: **com artigo** (`"art. N [qualificador] da/do
    <norma>"`, em qualquer ordem entre qualificador e artigo — `"inciso II do art. 37 da CF"` ou
    `"art. 37, caput, da CF"`) e **só norma** (`"Lei nº 14.133/2021"` sozinha, sem artigo
    anexado). Uma menção a artigo sem nenhuma norma junto (`"§ 1º do art. 37"` isolado) não gera
    referência — é ambígua, e a regra de ouro (ADR-0036) proíbe adivinhar qual norma seria.

    Args:
        texto: o texto onde procurar (enunciado + comando + texto de apoio de uma questão,
            concatenados por quem chama — esta função não sabe o que é uma questão).

    Returns:
        As referências únicas encontradas, na ordem em que aparecem no texto; lista vazia
        quando nada reconhecível aparece (o caso mais comum na base real).
    """
    referencias: list[ReferenciaLegal] = []
    vistos: set[tuple[str | None, str | None, str | None, str | None]] = set()
    spans_consumidos: list[tuple[int, int]] = []

    for artigo_match in _ARTIGO_NUCLEO.finditer(texto):
        resultado = _tentar_sufixo(texto, artigo_match.end())
        if resultado is None:
            continue
        fim, inciso_sufixo, paragrafo_sufixo, norma_id = resultado

        prefixo = _QUALIFICADOR_PREFIXO.search(texto[: artigo_match.start()])
        inciso_prefixo, paragrafo_prefixo = _partes_do_qualificador(prefixo)

        inicio_trecho = prefixo.start() if prefixo else artigo_match.start()
        inciso = inciso_sufixo or inciso_prefixo
        paragrafo = paragrafo_sufixo or paragrafo_prefixo
        numero = _normalizar_numero(artigo_match.group("numero"))

        chave = (norma_id, numero, inciso, paragrafo)
        spans_consumidos.append((inicio_trecho, fim))
        if chave in vistos:
            continue
        vistos.add(chave)
        referencias.append(
            ReferenciaLegal(
                norma=norma_id,
                artigo=numero,
                inciso=inciso,
                paragrafo=paragrafo,
                trecho=texto[inicio_trecho:fim],
            )
        )

    for norma_match in _NORMA.finditer(texto):
        if any(
            inicio <= norma_match.start() and norma_match.end() <= fim
            for inicio, fim in spans_consumidos
        ):
            continue
        norma_id = _norma_id(norma_match)
        chave_norma: tuple[str | None, str | None, str | None, str | None] = (
            norma_id,
            None,
            None,
            None,
        )
        if chave_norma in vistos:
            continue
        vistos.add(chave_norma)
        referencias.append(
            ReferenciaLegal(
                norma=norma_id,
                artigo=None,
                inciso=None,
                paragrafo=None,
                trecho=norma_match.group(0),
            )
        )

    return referencias
