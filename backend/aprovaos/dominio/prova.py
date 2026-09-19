"""Segmentação determinística de um caderno Cebraspe: texto → lista de itens (C/E e A–E).

O que é: `ItemBruto`/`segmentar_cebraspe` (linha "Cebraspe (C/E)" da tabela "Segmentação por
banca" da skill `ingestao-de-provas`) e `AlternativaBruta`/`ItemBrutoAlternativas`/
`segmentar_multipla_escolha` (linha "Cebraspe (A–E, cargos de nível médio)" da mesma tabela).
Funções puras, sem IA, sem rede, sem disco — quem lê o PDF (`dominio/pdf.extrair_texto`) é quem
chama. Quando ler: ao ajustar qualquer uma das duas segmentações para um caderno real que ela não
entendeu.

`segmentar_multipla_escolha` não reconhece "Texto para as questões X a Y" (bloco de apoio
compartilhado por várias questões) nem um comando compartilhado entre questões — o único caderno
A–E real disponível nesta fatia (`TJ_CE_23_SERVIDOR`, Técnico Judiciário) não usa nenhum dos
dois: cada questão é autocontida, com seu próprio enunciado terminado em "assinale a opção
correta" (ou equivalente). Ver `.superpowers/sdd/V3b-multipla-escolha/passo-1-report.md`.
"""

import re
from typing import Literal

from pydantic import BaseModel

from aprovaos.dominio.erros import SegmentacaoAmbigua

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


def _fronteiras_candidatas(linhas: list[str], minimo: int = 1) -> list[int]:
    """Acha, dentro de um bloco de linhas, todos os pontos onde uma frase nova com "julgue" começa.

    Uma fronteira candidata é uma linha que (a) é o início de uma frase — a linha anterior
    termina em ponto final e esta começa com maiúscula — e (b) o texto dali até o fim do bloco
    contém o verbo "julgue" (só um comando o usa; o enunciado de um item nunca usa). Um bloco
    pode ter mais de uma: um item de situação hipotética pode ter uma sentença extra antes do
    comando (candidata única) ou uma narrativa de apoio implícita, sem marcador "Texto para...",
    entre o fim do item e o comando (duas candidatas — a primeira fecha o enunciado, a segunda
    abre o comando). Quem decide o que fazer com cada quantidade é quem chama.

    Args:
        linhas: as linhas do bloco, na ordem.
        minimo: primeiro índice a considerar como possível fronteira; `1` nos blocos de item (o
            índice `0` é sempre conteúdo do item, nunca comando).

    Returns:
        Os índices de `linhas` onde uma fronteira começa, na ordem em que aparecem no bloco;
        lista vazia se o bloco inteiro é uma coisa só (nenhuma fronteira nova apareceu).
    """
    candidatas: list[int] = []
    for indice in range(minimo, len(linhas)):
        anterior = linhas[indice - 1]
        atual = linhas[indice]
        comeca_frase = anterior.endswith(".") and atual[:1] and atual[0].isupper()
        if not comeca_frase:
            continue
        cauda = " ".join(linhas[indice:])
        if _JULGUE.search(cauda):
            candidatas.append(indice)
    return candidatas


def _extrair_texto_apoio(
    linhas: list[str],
) -> tuple[list[str], dict[int, tuple[str, list[int]]]]:
    """Remove os blocos "Texto para os itens X a Y" das linhas e devolve o texto de cada um.

    O bloco entre o marcador e o início do primeiro item do intervalo pode conter, no fim, um
    comando (achado por `_fronteiras_candidatas`) — esse comando não é texto de apoio; ele volta
    para o fluxo de linhas normal, no lugar do bloco removido, para ser tratado como o comando
    do item seguinte. O padrão conhecido aqui tem **no máximo uma** fronteira (corpo do texto de
    apoio, opcionalmente seguido do comando); mais de uma é estrutura que a função não cobre.

    Args:
        linhas: linhas já sem cabeçalho/rodapé/marcador de seção.

    Returns:
        Uma tupla com as linhas sem o marcador nem o corpo do texto de apoio (mas com o comando,
        se houver, preservado no lugar) e um mapa `numero_item -> (texto_apoio, itens_do_bloco)`.

    Raises:
        SegmentacaoAmbigua: o bloco entre o marcador e o item tem mais de uma fronteira
            candidata — não dá para saber sozinho onde o texto de apoio termina.
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
        candidatas = _fronteiras_candidatas(bloco, minimo=1)
        if len(candidatas) > 1:
            raise SegmentacaoAmbigua(
                f"Bloco de texto de apoio dos itens {inicio_intervalo} a {fim_intervalo} tem "
                f"{len(candidatas)} fronteiras de comando candidatas (máximo tratado: 1) — "
                "revisão manual necessária."
            )
        linhas_apoio = bloco if not candidatas else bloco[: candidatas[0]]
        linhas_comando = [] if not candidatas else bloco[candidatas[0] :]
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


class _Segmento:
    """Um comando vigente (com ou sem apoio implícito) e os itens que o usam (uso interno).

    `itens` é preenchido conforme os itens são processados e continua mutável enquanto o
    segmento está vigente; depois que um novo segmento é aberto, o anterior nunca é tocado de
    novo — por isso é seguro montar o `ItemBruto` de cada item só no fim, lendo `itens` do seu
    próprio segmento já completo.
    """

    def __init__(self, comando: str | None, texto_apoio: str | None) -> None:
        self.comando = comando
        self.texto_apoio = texto_apoio
        self.itens: list[int] = []


def segmentar_cebraspe(texto: str) -> list[ItemBruto]:
    """Segmenta o texto de um caderno Cebraspe certo/errado em itens, sem IA e sem rede.

    Implementa a linha "Cebraspe (C/E)" da tabela "Segmentação por banca" da skill
    `ingestao-de-provas`: cada item começa com o número no início da linha; o comando vigente é
    a última instrução de julgamento ("julgue os itens...") encontrada antes dele e vale até o
    próximo comando aparecer. O texto de apoio pode vir de duas formas, e as duas viram
    `texto_apoio` dos itens do intervalo: um bloco marcado "Texto para os itens X a Y", ou uma
    narrativa de situação hipotética sem marcador nenhum, encontrada entre o fim do enunciado de
    um item e o comando que introduz os itens seguintes (duas fronteiras no mesmo bloco: a
    primeira fecha o enunciado de quem a antecede, a segunda abre o comando novo).

    Args:
        texto: texto do caderno, já extraído do PDF (`dominio.pdf.extrair_texto`).

    Returns:
        Os itens na ordem do caderno, com `numero_item` estritamente crescente e sem buracos
        quando o caderno em si não tiver buracos de numeração.

    Raises:
        SegmentacaoAmbigua: um bloco (de item ou de texto de apoio explícito) tem mais
            fronteiras de comando candidatas do que o padrão conhecido cobre.
    """
    linhas = _linhas_relevantes(texto)
    linhas, mapa_apoio_explicito = _extrair_texto_apoio(linhas)

    segmento_atual = _Segmento(comando=None, texto_apoio=None)
    pendentes: list[tuple[int, str, _Segmento]] = []  # (numero, enunciado, segmento_do_item)

    for numero, linhas_do_bloco in _blocos_por_item(linhas):
        if numero is None:
            texto_preambulo = _juntar(linhas_do_bloco)
            if texto_preambulo and _JULGUE.search(texto_preambulo):
                segmento_atual.comando = texto_preambulo
            continue

        candidatas = _fronteiras_candidatas(linhas_do_bloco, minimo=1)
        if len(candidatas) > 2:
            raise SegmentacaoAmbigua(
                f"Bloco do item {numero} tem {len(candidatas)} fronteiras de comando "
                "candidatas (máximo tratado: 2 — enunciado + narrativa de apoio implícita) — "
                "revisão manual necessária."
            )

        fim_do_enunciado = candidatas[0] if candidatas else len(linhas_do_bloco)
        linhas_enunciado = linhas_do_bloco[:fim_do_enunciado]
        primeira_linha = _INICIO_DE_ITEM.sub("", linhas_enunciado[0], count=1)
        enunciado = _juntar([primeira_linha, *linhas_enunciado[1:]])
        pendentes.append((numero, enunciado, segmento_atual))
        segmento_atual.itens.append(numero)

        if len(candidatas) == 1:
            comando_novo = _juntar(linhas_do_bloco[candidatas[0] :])
            segmento_atual = _Segmento(comando=comando_novo, texto_apoio=None)
        elif len(candidatas) == 2:
            apoio_implicito = _juntar(linhas_do_bloco[candidatas[0] : candidatas[1]])
            comando_novo = _juntar(linhas_do_bloco[candidatas[1] :])
            segmento_atual = _Segmento(comando=comando_novo, texto_apoio=apoio_implicito)

    itens: list[ItemBruto] = []
    for numero, enunciado, segmento in pendentes:
        if numero in mapa_apoio_explicito:
            texto_apoio, itens_do_apoio = mapa_apoio_explicito[numero]
        elif segmento.texto_apoio is not None:
            texto_apoio, itens_do_apoio = segmento.texto_apoio, list(segmento.itens)
        else:
            texto_apoio, itens_do_apoio = None, []
        itens.append(
            ItemBruto(
                numero_item=numero,
                comando=segmento.comando,
                texto_apoio=texto_apoio,
                texto_apoio_itens=itens_do_apoio,
                enunciado=enunciado,
            )
        )
    return itens


_LETRA = Literal["A", "B", "C", "D", "E"]
_LETRAS_ALTERNATIVA: tuple[_LETRA, ...] = ("A", "B", "C", "D", "E")

_INICIO_DE_QUESTAO = re.compile(r"(?i)^Questão\s+(\d+)$")
"""Cabeçalho de questão do caderno A–E, ex.: "Questão 21" (a Cebraspe imprime em title case;
a skill descreve o marcador como "QUESTÃO N" — a comparação é sem diferenciar caixa)."""

_MARCADOR_DE_ALTERNATIVA = re.compile(r"^([A-E])\s+(?=\S)")
"""Letra da alternativa no início da linha, seguida de espaço e conteúdo.

Uma letra maiúscula sozinha no início de uma linha também aparece por acaso como artigo
("A República..." ) ou conjunção ("E, ainda, ...") no meio do enunciado — por isso esta regex só
identifica *candidatos*; `_indices_das_alternativas` é quem decide, por eliminação posicional
(cada letra tem de aparecer antes da seguinte já resolvida), qual candidato é a alternativa de
verdade. Ver achado do passo 1 no relatório da fatia."""

_CABECALHO_MULTIPLA_ESCOLHA = re.compile(r"(?i)CEBRASPE")
"""Cabeçalho repetido a cada página do caderno A–E, ex.: "82000101135697 CEBRASPE – TJ/CE –
SERVIDOR – Edital: 2023" — ao contrário do caderno C/E, vem com um código numérico antes, por
isso a busca é por conter "CEBRASPE" em qualquer posição da linha, não por começar com ele."""

_ESPACO_LIVRE = re.compile(r"(?i)^Espaço livre$")
"""Marcador de preenchimento de página do caderno A–E, sem conteúdo — nunca item nem alternativa."""


class AlternativaBruta(BaseModel):
    """Uma alternativa (A–E) tal como o caderno a imprime, ainda sem saber se é o gabarito.

    Attributes:
        letra: a letra impressa da alternativa.
        texto: o texto da alternativa, linhas reunidas (hífen de quebra resolvido).
    """

    letra: _LETRA
    texto: str


class ItemBrutoAlternativas(BaseModel):
    """Uma questão de múltipla escolha A–E tal como o caderno a apresenta, sem gabarito nem tópico.

    Attributes:
        numero_item: número da questão impresso no caderno (ex.: `21`).
        enunciado: o texto da questão até a primeira alternativa, como o caderno imprimiu — inclui
            qualquer instrução final embutida (ex.: "assinale a opção correta"), porque, no único
            caderno real desta fatia, essa instrução não é um comando reaproveitado por outras
            questões (ver módulo).
        alternativas: as cinco alternativas, na ordem A, B, C, D, E.
    """

    numero_item: int
    enunciado: str
    alternativas: list[AlternativaBruta]


def _linhas_relevantes_multipla_escolha(texto: str) -> list[str]:
    """Divide o texto em linhas e descarta cabeçalho, rodapé, marcador de seção e "Espaço livre".

    Args:
        texto: texto integral extraído do PDF do caderno A–E.

    Returns:
        As linhas com conteúdo, já sem as pontas em branco, na ordem do caderno.
    """
    linhas: list[str] = []
    for bruta in texto.split("\n"):
        linha = bruta.strip()
        if not linha:
            continue
        if _CABECALHO_MULTIPLA_ESCOLHA.search(linha):
            continue
        if _MARCADOR_DE_SECAO.match(linha):
            continue
        if _ESPACO_LIVRE.match(linha):
            continue
        linhas.append(linha)
    return linhas


def _blocos_por_questao(linhas: list[str]) -> list[tuple[int | None, list[str]]]:
    """Agrupa as linhas em blocos: um preâmbulo (sem questão) e um por questão.

    Args:
        linhas: linhas já sem cabeçalho/rodapé/marcador de seção/"Espaço livre".

    Returns:
        Uma lista de `(numero_item, linhas_do_bloco)`; o primeiro elemento tem `numero_item`
        `None` quando há texto antes da primeira questão.
    """
    blocos: list[tuple[int | None, list[str]]] = []
    numero_atual: int | None = None
    linhas_atuais: list[str] = []
    for linha in linhas:
        casamento = _INICIO_DE_QUESTAO.match(linha)
        if casamento is not None:
            blocos.append((numero_atual, linhas_atuais))
            numero_atual = int(casamento.group(1))
            linhas_atuais = []
        else:
            linhas_atuais.append(linha)
    blocos.append((numero_atual, linhas_atuais))
    return blocos


def _indices_das_alternativas(linhas: list[str], numero_item: int) -> dict[_LETRA, int]:
    """Acha, num bloco de questão, o índice de cada alternativa A–E, por eliminação posicional.

    Junta todos os candidatos (linhas que começam com uma letra A–E seguida de espaço) e resolve
    da direita para a esquerda: a alternativa E é o último candidato "E" do bloco; a D é o último
    candidato "D" que vem antes da E já resolvida; e assim por diante até A. Isso decide sozinho,
    sem adivinhar, qual candidato "A" é a alternativa de verdade quando o enunciado da questão
    começa com o artigo "A" (achado do passo 1: 5 das 40 questões do caderno real começam assim).

    Args:
        linhas: as linhas do bloco da questão (sem a própria linha "Questão N").
        numero_item: número da questão, só para a mensagem de erro.

    Returns:
        Um mapa `letra -> índice`, com os cinco índices em ordem estritamente crescente.

    Raises:
        SegmentacaoAmbigua: alguma letra não tem candidato, ou não tem candidato antes da letra
            seguinte já resolvida — estrutura de alternativas não reconhecida.
    """
    candidatos: dict[_LETRA, list[int]] = {letra: [] for letra in _LETRAS_ALTERNATIVA}
    for indice, linha in enumerate(linhas):
        casamento = _MARCADOR_DE_ALTERNATIVA.match(linha)
        if casamento is not None:
            letra_encontrada = casamento.group(1)
            assert letra_encontrada in _LETRAS_ALTERNATIVA  # regex só casa A-E
            candidatos[letra_encontrada].append(indice)

    faltando = [letra for letra in _LETRAS_ALTERNATIVA if not candidatos[letra]]
    if faltando:
        raise SegmentacaoAmbigua(
            f"Questão {numero_item}: não encontrei a(s) alternativa(s) {', '.join(faltando)} — "
            "estrutura de alternativas não reconhecida."
        )

    indices: dict[_LETRA, int] = {"E": candidatos["E"][-1]}
    limite = indices["E"]
    for letra in ("D", "C", "B", "A"):
        anteriores = [indice for indice in candidatos[letra] if indice < limite]
        if not anteriores:
            raise SegmentacaoAmbigua(
                f"Questão {numero_item}: a alternativa {letra} não aparece antes da alternativa "
                "seguinte já resolvida — estrutura de alternativas não reconhecida."
            )
        indices[letra] = anteriores[-1]
        limite = indices[letra]
    return indices


def segmentar_multipla_escolha(texto: str) -> list[ItemBrutoAlternativas]:
    """Segmenta o texto de um caderno Cebraspe A–E (nível médio) em questões, sem IA e sem rede.

    Implementa a linha "Cebraspe (A–E, cargos de nível médio)" da tabela "Segmentação por banca"
    da skill `ingestao-de-provas`: cada questão começa em uma linha "Questão N"; o enunciado é o
    texto até a primeira alternativa; as cinco alternativas são identificadas por eliminação
    posicional (`_indices_das_alternativas`).

    Args:
        texto: texto do caderno, já extraído do PDF (`dominio.pdf.extrair_texto`).

    Returns:
        As questões na ordem do caderno, cada uma com exatamente cinco alternativas (A a E).

    Raises:
        SegmentacaoAmbigua: uma questão não tem as cinco alternativas reconhecíveis na ordem
            esperada — a função para em vez de adivinhar; o documento fica para revisão manual.
    """
    linhas = _linhas_relevantes_multipla_escolha(texto)
    itens: list[ItemBrutoAlternativas] = []
    for numero, linhas_do_bloco in _blocos_por_questao(linhas):
        if numero is None:
            continue
        indices = _indices_das_alternativas(linhas_do_bloco, numero)
        enunciado = _juntar(linhas_do_bloco[: indices["A"]])
        limites = [indices[letra] for letra in _LETRAS_ALTERNATIVA] + [len(linhas_do_bloco)]
        alternativas: list[AlternativaBruta] = []
        for posicao, letra in enumerate(_LETRAS_ALTERNATIVA):
            inicio, fim = limites[posicao], limites[posicao + 1]
            primeira_linha = _MARCADOR_DE_ALTERNATIVA.sub("", linhas_do_bloco[inicio], count=1)
            texto_alternativa = _juntar([primeira_linha, *linhas_do_bloco[inicio + 1 : fim]])
            alternativas.append(AlternativaBruta(letra=letra, texto=texto_alternativa))
        itens.append(
            ItemBrutoAlternativas(
                numero_item=numero, enunciado=enunciado, alternativas=alternativas
            )
        )
    return itens
