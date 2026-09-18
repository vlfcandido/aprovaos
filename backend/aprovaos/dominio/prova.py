"""Segmentação determinística de um caderno Cebraspe certo/errado: texto → lista de itens.

O que é: `ItemBruto` (Pydantic) e `segmentar_cebraspe(texto: str) -> list[ItemBruto]`, que
implementam a linha "Cebraspe (C/E)" da tabela "Segmentação por banca" da skill
`ingestao-de-provas`. Função pura, sem IA, sem rede, sem disco — quem lê o PDF
(`dominio/pdf.extrair_texto`) é quem chama. Quando ler: ao ajustar a segmentação para um
caderno C/E real que ela não entendeu, ou ao estender para o padrão A–E (fora desta fatia).
"""

import re

from pydantic import BaseModel

# Maiúsculas latinas com acento (faixa Latin-1 À–Ý) — usadas para reconhecer o início de uma
# frase nova (item ou comando), nunca a continuação de uma frase quebrada pelo PDF.
_MAIUSCULA = "A-ZÀ-Ý"

_INICIO_DE_ITEM = re.compile(rf"^(\d{{1,3}})\s+(?=[{_MAIUSCULA}])")
"""Número do item no início da linha, seguido de espaço e de letra maiúscula.

A letra maiúscula depois do espaço é o que distingue um item real ("58 O diálogo...") de uma
continuação de linha que por acaso começa com dígito e minúscula (ex.: "2 a 4 anos.", meio de
uma frase quebrada pelo PDF) — sem essa exigência, essa quebra vira um item fantasma.
"""

_TEXTO_DE_APOIO = re.compile(
    r"(?i)^texto\s+para\s+(?:o\s+item|os\s+itens)\s+(\d+)(?:\s*(?:a|e)\s*(\d+))?"
)
"""Marcador "Texto para o item N" / "Texto para os itens X a Y" / "... X e Y"."""

_CABECALHO_CEBRASPE = re.compile(r"^CEBRASPE\b", re.IGNORECASE)
"""Cabeçalho repetido a cada página, ex.: "CEBRASPE – TJ_PA_SERVIDOR – Edital: 2025"."""

_MARCADOR_DE_SECAO = re.compile(r"^-{2,}.*$")
"""Título decorativo de seção, ex.: "-- CONHECIMENTOS ESPECÍFICOS – "."""

_NUMERO_DE_PAGINA = re.compile(r"^\d{1,3}$")
"""Linha com só um número (rodapé de paginação); nunca um item, que sempre tem texto atrás."""

_JULGUE = re.compile(r"(?i)\bjulgue\b")
"""Verbo que só aparece no comando ("julgue os itens..."), nunca no enunciado de um item."""


class ItemBruto(BaseModel):
    """Um item C/E tal como o texto do caderno o apresenta, ainda sem gabarito nem tópico.

    Attributes:
        numero_item: número do item impresso no caderno (ex.: `58`).
        comando: a instrução de julgamento vigente para este item ("julgue os itens..."), ou
            `None` se nenhum comando foi encontrado antes dele.
        texto_apoio: o texto-base de um bloco "Texto para os itens X a Y", ou `None` se o item
            não pertence a nenhum bloco desses.
        texto_apoio_itens: todos os números do intervalo do bloco de apoio (inclui o próprio
            item), ou lista vazia se `texto_apoio` é `None`.
        enunciado: a afirmação a ser julgada, como o caderno imprimiu (linhas reunidas, hífen
            de quebra de linha resolvido — nenhuma outra normalização).
    """

    numero_item: int
    comando: str | None
    texto_apoio: str | None
    texto_apoio_itens: list[int]
    enunciado: str


def _linhas_relevantes(texto: str) -> list[str]:
    """Divide o texto em linhas e descarta cabeçalho, rodapé, marcador de seção e linhas vazias.

    Args:
        texto: texto integral extraído do PDF do caderno.

    Returns:
        As linhas com conteúdo, já sem as pontas em branco, na ordem do caderno.
    """
    linhas: list[str] = []
    for bruta in texto.split("\n"):
        linha = bruta.strip()
        if not linha:
            continue
        if _CABECALHO_CEBRASPE.match(linha):
            continue
        if _MARCADOR_DE_SECAO.match(linha):
            continue
        if _NUMERO_DE_PAGINA.match(linha):
            continue
        linhas.append(linha)
    return linhas


def _juntar(linhas: list[str]) -> str:
    """Reúne linhas quebradas pelo PDF num texto só, resolvendo hífen de quebra de palavra.

    Linha terminada em hífen seguida de linha iniciada em minúscula é uma palavra partida pela
    justificação do PDF ("constitu-" + "cionalidade"): junta sem espaço e sem o hífen. Qualquer
    outro par de linhas junta com um espaço simples. Nenhuma outra normalização — o texto é o
    que a banca imprimiu.

    Args:
        linhas: linhas já sem cabeçalho/rodapé, na ordem em que aparecem no caderno.

    Returns:
        O texto reunido; string vazia se `linhas` está vazia.
    """
    texto = ""
    for linha in linhas:
        if not texto:
            texto = linha
        elif texto.endswith("-") and linha[:1].islower():
            texto = texto[:-1] + linha
        else:
            texto = f"{texto} {linha}"
    return texto


def _fronteira_do_comando(linhas: list[str], minimo: int = 1) -> int | None:
    """Acha onde, dentro de um bloco de linhas, começa um comando novo (se houver).

    Um comando novo começa numa linha que (a) é o início de uma frase — a linha anterior termina
    em ponto final e esta começa com maiúscula — e (b) o texto dali até o fim do bloco contém o
    verbo "julgue" (só o comando o usa; o enunciado de um item nunca usa). Entre todas as
    posições que satisfazem isso, a função devolve a última (a mais próxima do fim do bloco) —
    é o que mantém no item toda frase que lhe pertence, mesmo quando o item tem mais de uma
    frase (ex.: um enunciado de situação hipotética), e isola só o comando de fato.

    Args:
        linhas: as linhas do bloco, na ordem.
        minimo: primeiro índice a considerar como possível início de comando; `1` nos blocos de
            item (o índice `0` é sempre conteúdo do item, nunca comando).

    Returns:
        O índice de `linhas` onde o comando começa, ou `None` se o bloco inteiro é conteúdo do
        item (nenhum comando novo apareceu).
    """
    fronteira: int | None = None
    for indice in range(minimo, len(linhas)):
        anterior = linhas[indice - 1]
        atual = linhas[indice]
        comeca_frase = anterior.endswith(".") and atual[:1] and atual[0].isupper()
        if not comeca_frase:
            continue
        cauda = " ".join(linhas[indice:])
        if _JULGUE.search(cauda):
            fronteira = indice
    return fronteira


def _extrair_texto_apoio(
    linhas: list[str],
) -> tuple[list[str], dict[int, tuple[str, list[int]]]]:
    """Remove os blocos "Texto para os itens X a Y" das linhas e devolve o texto de cada um.

    O bloco entre o marcador e o início do primeiro item do intervalo pode conter, no fim, um
    comando (achado por `_fronteira_do_comando`) — esse comando não é texto de apoio; ele volta
    para o fluxo de linhas normal, no lugar do bloco removido, para ser tratado como o comando
    do item seguinte.

    Args:
        linhas: linhas já sem cabeçalho/rodapé/marcador de seção.

    Returns:
        Uma tupla com as linhas sem o marcador nem o corpo do texto de apoio (mas com o comando,
        se houver, preservado no lugar) e um mapa `numero_item -> (texto_apoio, itens_do_bloco)`.
    """
    resultado: list[str] = []
    mapa: dict[int, tuple[str, list[int]]] = {}
    indice = 0
    while indice < len(linhas):
        casamento = _TEXTO_DE_APOIO.match(linhas[indice])
        if casamento is None:
            resultado.append(linhas[indice])
            indice += 1
            continue
        inicio_intervalo = int(casamento.group(1))
        fim_intervalo = int(casamento.group(2)) if casamento.group(2) else inicio_intervalo
        fim_bloco = indice + 1
        while fim_bloco < len(linhas) and _INICIO_DE_ITEM.match(linhas[fim_bloco]) is None:
            fim_bloco += 1
        bloco = linhas[indice + 1 : fim_bloco]
        fronteira = _fronteira_do_comando(bloco, minimo=1) if len(bloco) > 1 else None
        linhas_apoio = bloco if fronteira is None else bloco[:fronteira]
        linhas_comando = [] if fronteira is None else bloco[fronteira:]
        texto_apoio = _juntar(linhas_apoio)
        itens_do_bloco = list(range(inicio_intervalo, fim_intervalo + 1))
        for numero in itens_do_bloco:
            mapa[numero] = (texto_apoio, itens_do_bloco)
        resultado.extend(linhas_comando)
        indice = fim_bloco
    return resultado, mapa


def _blocos_por_item(linhas: list[str]) -> list[tuple[int | None, list[str]]]:
    """Agrupa as linhas em blocos: um preâmbulo (sem item) e um por item, pelo início de cada um.

    Args:
        linhas: linhas já sem cabeçalho/rodapé/marcador de seção/texto de apoio.

    Returns:
        Uma lista de `(numero_item, linhas_do_bloco)`; o primeiro elemento tem `numero_item`
        `None` quando há texto antes do primeiro item (o comando inicial do caderno).
    """
    blocos: list[tuple[int | None, list[str]]] = []
    numero_atual: int | None = None
    linhas_atuais: list[str] = []
    for linha in linhas:
        casamento = _INICIO_DE_ITEM.match(linha)
        if casamento is not None:
            blocos.append((numero_atual, linhas_atuais))
            numero_atual = int(casamento.group(1))
            linhas_atuais = [linha]
        else:
            linhas_atuais.append(linha)
    blocos.append((numero_atual, linhas_atuais))
    return blocos


def segmentar_cebraspe(texto: str) -> list[ItemBruto]:
    """Segmenta o texto de um caderno Cebraspe certo/errado em itens, sem IA e sem rede.

    Implementa a linha "Cebraspe (C/E)" da tabela "Segmentação por banca" da skill
    `ingestao-de-provas`: cada item começa com o número no início da linha; o comando vigente é
    a última instrução de julgamento ("julgue os itens...") encontrada antes dele e vale até o
    próximo comando aparecer; um bloco "Texto para os itens X a Y" vira `texto_apoio` de cada
    item do intervalo.

    Args:
        texto: texto do caderno, já extraído do PDF (`dominio.pdf.extrair_texto`).

    Returns:
        Os itens na ordem do caderno, com `numero_item` estritamente crescente e sem buracos
        quando o caderno em si não tiver buracos de numeração.
    """
    linhas = _linhas_relevantes(texto)
    linhas, mapa_apoio = _extrair_texto_apoio(linhas)
    itens: list[ItemBruto] = []
    comando_atual: str | None = None
    for numero, linhas_do_bloco in _blocos_por_item(linhas):
        if numero is None:
            texto_preambulo = _juntar(linhas_do_bloco)
            if texto_preambulo and _JULGUE.search(texto_preambulo):
                comando_atual = texto_preambulo
            continue
        fronteira = _fronteira_do_comando(linhas_do_bloco, minimo=1)
        linhas_enunciado = linhas_do_bloco if fronteira is None else linhas_do_bloco[:fronteira]
        linhas_comando_novo = [] if fronteira is None else linhas_do_bloco[fronteira:]
        primeira_linha = _INICIO_DE_ITEM.sub("", linhas_enunciado[0], count=1)
        enunciado = _juntar([primeira_linha, *linhas_enunciado[1:]])
        texto_apoio, itens_do_apoio = mapa_apoio.get(numero, (None, []))
        itens.append(
            ItemBruto(
                numero_item=numero,
                comando=comando_atual,
                texto_apoio=texto_apoio,
                texto_apoio_itens=itens_do_apoio,
                enunciado=enunciado,
            )
        )
        if linhas_comando_novo:
            comando_atual = _juntar(linhas_comando_novo)
    return itens
