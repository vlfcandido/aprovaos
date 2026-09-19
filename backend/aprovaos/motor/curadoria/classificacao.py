"""Classificação de tópico: léxico por regras e IA em lote, com fallback item a item.

O que é: `Classificacao` (o contrato da skill `ingestao-de-provas`, seção "Classificação de
tópico"), `TopicoVocabulario`/`ItemParaClassificar` (o vocabulário e os itens do lote,
desacoplados do ORM — quem traduz `TopicoEdital`/`ItemBruto` para eles é quem chama, na
orquestração real), a porta `ClassificadorDeTopico`, `classificar_por_regras`/
`ClassificadorPorRegras` (léxico do `texto_original` de cada tópico + número de lei citado) e
`classificar` (IA em lote → cada item confere → regras onde faltar, nunca bloqueia — mesmo
desenho de `agentes.analista_de_edital.gerar_dna`). Quando ler: ao ligar a classificação num
pipeline de curadoria, ao ajustar o léxico para um edital real que ele não cobre, ou ao
investigar por que um item saiu "por regras" (`Classificacao.motivo_fallback`).
"""

import json
import re
import unicodedata
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ValidationError

Confianca = Literal["alta", "media", "baixa"]

#: Evidência fixa quando nenhum termo do léxico nem lei citada casa com o item (contrato da
#: skill `ingestao-de-provas`).
SEM_CORRESPONDENCIA = "sem correspondência no vocabulário"

#: Motivo de fallback quando a IA classificou o lote mas não devolveu entrada para um item.
ITEM_AUSENTE = "item ausente na resposta do modelo"

#: Confiança do léxico por regras quando o único casamento achado foi uma palavra isolada do
#: `texto_original` de um tópico (Ruling 21, rodada 1 de correção do passo 8): uma palavra só é
#: comum demais no vocabulário jurídico para decidir sozinha — vira `"baixa"`, sem `topico_slug`,
#: em vez de `"media"`.
_TERMO_ISOLADO_NAO_BASTA = (
    'termo isolado "{termo}" (tópico {slug}) não basta para classificar — é preciso frase de '
    "2 ou mais palavras"
)

_CERCA_DE_CODIGO = re.compile(r"\A```[a-zA-Z]*\s*\n?(.*?)\n?```\Z", re.DOTALL)


class ClassificacaoInvalida(ValueError):
    """A resposta da IA não é aproveitável: não é JSON, ou não é uma lista.

    Levantada por `interpretar_resposta` só quando **nenhuma** entrada é recuperável — corpo
    malformado ou fora do formato esperado. Uma entrada individual com `topico_slug` fora do
    vocabulário, ou com campo faltando, **não** levanta esta exceção: ela é só rejeitada (ver o
    segundo item da tupla que `interpretar_resposta` devolve), sem derrubar as outras entradas
    boas da mesma resposta. Nunca escapa até o aluno — `classificar` cai para regras no que não
    deu (mesmo espírito de `gerar_dna`: uma chamada que falhou vale regras para o lote inteiro).
    """


class TopicoVocabulario(BaseModel):
    """Um tópico do vocabulário canônico do edital, desacoplado do ORM.

    Attributes:
        slug: identificador estável do tópico — o único valor que `topico_slug` pode assumir;
            nunca inventado pelo classificador.
        materia: slug da matéria a que o tópico pertence.
        texto_original: o texto do item do conteúdo programático, como está no edital.
    """

    slug: str
    materia: str
    texto_original: str


class ItemParaClassificar(BaseModel):
    """Um item de prova a classificar, no mínimo necessário para decidir o tópico.

    Attributes:
        numero_item: número do item no caderno — identifica a linha correspondente na resposta
            em lote.
        comando: a instrução de julgamento vigente para o item, ou `None` quando o caderno não
            tiver comando (raro).
        enunciado: a afirmação a ser julgada.
    """

    numero_item: int
    comando: str | None
    enunciado: str


class Classificacao(BaseModel):
    """O tópico decidido para um item, com evidência e confiança — contrato da skill.

    Attributes:
        numero_item: número do item classificado.
        topico_slug: slug do vocabulário canônico, ou `None` sem correspondência.
        confianca: `alta` (lei citada no item bate com a do tópico), `media` (termo do léxico do
            tópico apareceu no item) ou `baixa` (sem correspondência).
        evidencia: o que no texto decidiu — a lei citada, o termo casado, ou
            `SEM_CORRESPONDENCIA`.
        origem: `regras` ou `ia`.
        motivo_fallback: por que este item saiu por regras apesar de haver IA no lote (erro na
            chamada, resposta fora do contrato ou item ausente na resposta); `None` quando não
            havia IA para tentar, ou quando `origem == "ia"`.
    """

    numero_item: int
    topico_slug: str | None
    confianca: Confianca
    evidencia: str
    origem: Literal["regras", "ia"]
    motivo_fallback: str | None = None


class ResultadoClassificacao(BaseModel):
    """O que `classificar` devolve para um lote: uma `Classificacao` por item de entrada.

    Attributes:
        classificacoes: uma por item de `itens`, na mesma ordem, cada uma com a própria
            `origem`.
    """

    classificacoes: list[Classificacao]


#: Motivo por `numero_item`: por que uma entrada da resposta foi rejeitada (slug fora do
#: vocabulário, campo faltando/tipo errado) e não virou uma `Classificacao` de origem IA.
MotivosRejeicao = dict[int, str]


@runtime_checkable
class ClassificadorDeTopico(Protocol):
    """Porta do classificador.

    Recebe o lote e o vocabulário e devolve uma classificação por item.
    """

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]
    ) -> tuple[list[Classificacao], MotivosRejeicao]:
        """Classifica todo o lote de uma vez.

        Args:
            itens: os itens do lote (até `config.lote_classificacao`).
            vocabulario: os tópicos do conteúdo programático do edital.

        Returns:
            `(classificacoes, motivos_rejeicao)`: uma `Classificacao` por item que a
            implementação conseguiu decidir com confiança na própria resposta, e o motivo de
            cada item que ela tentou decidir mas rejeitou (ex.: slug fora do vocabulário). Um
            item que não aparece em nenhum dos dois é tratado por quem chama como "sem resposta
            para ele" (`ITEM_AUSENTE`).
        """
        ...


def montar_lotes(itens: int, tamanho: int) -> list[int]:
    """Divide uma quantidade de itens em lotes de até `tamanho`, na ordem.

    Args:
        itens: quantidade total de itens a classificar (ex.: os itens de um caderno).
        tamanho: tamanho máximo de cada lote (`config.lote_classificacao`).

    Returns:
        Os tamanhos de cada lote, em ordem, com o resto no último; soma igual a `itens`. Lista
        vazia se `itens` for zero ou negativo.
    """
    if itens <= 0:
        return []
    cheios, resto = divmod(itens, tamanho)
    lotes = [tamanho] * cheios
    if resto:
        lotes.append(resto)
    return lotes


class _EntradaBruta(BaseModel):
    """Uma entrada crua da resposta da IA, antes de virar `Classificacao` (uso interno)."""

    numero_item: int
    topico_slug: str | None
    confianca: Confianca
    evidencia: str


def interpretar_resposta(
    texto: str, slugs_validos: set[str]
) -> tuple[list[Classificacao], MotivosRejeicao]:
    """Converte a resposta do lote (JSON) em `Classificacao`, entrada a entrada.

    Cada entrada da lista é validada por si: uma entrada com a forma certa e `topico_slug` do
    vocabulário vira `Classificacao` (`origem="ia"`); uma entrada com `topico_slug` fora do
    vocabulário, ou com campo faltando/tipo errado, é **rejeitada** — não vira `Classificacao`,
    mas também não derruba as outras entradas da mesma resposta (correção do passo 8, rodada 1:
    "aquele item cai para regras", não o lote inteiro).

    Args:
        texto: resposta bruta do modelo (JSON, possivelmente entre cerca de código).
        slugs_validos: os slugs do vocabulário enviado no lote — nenhum `topico_slug` fora
            disso é aceito.

    Returns:
        `(classificacoes, motivos_rejeicao)`: as `Classificacao` válidas (`origem="ia"`), na
        ordem em que vieram, e um mapa `numero_item -> motivo` para as entradas rejeitadas que
        ao menos traziam um `numero_item` legível. Pode ter menos entradas do que o lote pedido
        (nem toda entrada rejeitada tem `numero_item` reconhecível) — quem chama (`classificar`)
        decide o que fazer com o que faltou.

    Raises:
        ClassificacaoInvalida: a resposta inteira não é aproveitável — não é JSON, ou não é uma
            lista (nenhuma entrada individual para tentar validar).
    """
    limpo = texto.strip()
    cercado = _CERCA_DE_CODIGO.match(limpo)
    if cercado is not None:
        limpo = cercado.group(1).strip()
    try:
        bruto = json.loads(limpo)
    except json.JSONDecodeError as erro:
        raise ClassificacaoInvalida(f"resposta não é JSON: {erro}") from erro
    if not isinstance(bruto, list):
        raise ClassificacaoInvalida("resposta não é uma lista JSON de entradas")

    classificacoes: list[Classificacao] = []
    motivos_rejeicao: MotivosRejeicao = {}
    for entrada_bruta in bruto:
        numero_item = entrada_bruta.get("numero_item") if isinstance(entrada_bruta, dict) else None
        try:
            entrada = _EntradaBruta.model_validate(entrada_bruta)
        except ValidationError as erro:
            if isinstance(numero_item, int):
                motivos_rejeicao[numero_item] = f"resposta fora do contrato: {erro}"
            continue
        if entrada.topico_slug is not None and entrada.topico_slug not in slugs_validos:
            motivo = f"slug fora do vocabulário: {entrada.topico_slug}"
            motivos_rejeicao[entrada.numero_item] = motivo
            continue
        classificacoes.append(
            Classificacao(
                numero_item=entrada.numero_item,
                topico_slug=entrada.topico_slug,
                confianca=entrada.confianca,
                evidencia=entrada.evidencia,
                origem="ia",
            )
        )
    return classificacoes, motivos_rejeicao


# --- Léxico por regras -------------------------------------------------------------------

_STOPWORDS = frozenset(
    {
        "de",
        "da",
        "do",
        "das",
        "dos",
        "e",
        "a",
        "o",
        "as",
        "os",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "com",
        "para",
        "por",
        "sem",
        "sob",
        "sobre",
        "um",
        "uma",
        "uns",
        "umas",
        "ou",
        "que",
        "se",
    }
)

_PREFIXO_NUMERO = re.compile(r"^\d+\.\s*")
_PARENTESES = re.compile(r"\([^)]*\)")
_SEPARADOR_DE_NUCLEO = re.compile(r"[—:]")
_SEPARADOR_DE_CANDIDATO = re.compile(r",|\s+e\s+")
_LEI_REGEX = re.compile(r"lei\s*n[°º.]*\s*(\d{1,3}(?:\.\d{3})*)\s*/\s*(\d{4})", re.IGNORECASE)

# art. 37 da CF/88 lista, no próprio caput, os cinco princípios expressos da administração
# pública (legalidade, impessoalidade, moralidade, publicidade, eficiência). Quando o
# `texto_original` de um tópico cita esse artigo, esses cinco termos entram no léxico: é o texto
# do dispositivo citado, não uma invenção do classificador — a única exceção ao princípio "léxico
# só do texto_original + lei citada" (decisão do passo 8).
_ENRIQUECIMENTO_POR_MARCADOR: dict[str, list[str]] = {
    "art. 37": ["legalidade", "impessoalidade", "moralidade", "publicidade", "eficiencia"],
}


def _normalizar(texto: str) -> str:
    """Minúsculas e sem acento — a mesma normalização para o léxico e para o texto do item."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower()


def _leis_no_texto(texto: str) -> set[str]:
    """Todas as citações "Lei nº X/AAAA" do texto, normalizadas como `"X/AAAA"`."""
    return {f"{numero}/{ano}" for numero, ano in _LEI_REGEX.findall(texto)}


def _termos_do_topico(texto_original: str) -> tuple[list[str], list[str]]:
    """Os termos do léxico de um tópico: o núcleo do `texto_original`, partido em candidatos.

    O núcleo é o texto sem o número do item, sem parênteses (citações de artigo) e só até o
    primeiro `:`/`—` (o que vem depois costuma ser a lista de subitens, não o nome do tópico).
    Cada candidato (separado por vírgula ou por " e ") vira um termo do léxico, normalizado,
    desde que tenha pelo menos uma palavra fora da lista de conectivos.

    Um candidato com 2 ou mais palavras significativas é uma **frase de média confiança**.
    Um candidato reduzido a 1 palavra só entra se tiver 6 letras ou mais, e vira um **termo
    isolado**: sozinho, uma palavra é comum demais no vocabulário jurídico para decidir um
    tópico (Ruling 21) — por isso fica separado das frases, não soma confiança "media".

    Os termos de `_ENRIQUECIMENTO_POR_MARCADOR` são a única exceção: mesmo sendo uma palavra
    só, são curados a dedo (o texto do próprio artigo citado) e entram como frase de média
    confiança, não como termo isolado.

    Returns:
        `(frases_media, termos_isolados)`.
    """
    sem_numero = _PREFIXO_NUMERO.sub("", texto_original).strip()
    marcadores = [m for m in _ENRIQUECIMENTO_POR_MARCADOR if m in sem_numero.lower()]
    sem_parenteses = _PARENTESES.sub("", sem_numero)
    nucleo = _SEPARADOR_DE_NUCLEO.split(sem_parenteses, maxsplit=1)[0]
    frases_media: list[str] = []
    termos_isolados: list[str] = []
    for candidato in _SEPARADOR_DE_CANDIDATO.split(nucleo):
        normalizado = _normalizar(candidato).strip(" .")
        if not normalizado:
            continue
        palavras = normalizado.split()
        significativas = [p for p in palavras if p not in _STOPWORDS]
        if not significativas:
            continue
        if len(significativas) == 1:
            if len(significativas[0]) >= 6:
                termos_isolados.append(normalizado)
            continue
        frases_media.append(normalizado)
    for marcador in marcadores:
        frases_media.extend(_ENRIQUECIMENTO_POR_MARCADOR[marcador])
    return frases_media, termos_isolados


def _leis_do_topico(texto_original: str) -> list[str]:
    """As leis citadas no `texto_original` de um tópico, normalizadas como `"X/AAAA"`."""
    return sorted(_leis_no_texto(texto_original))


class _Lexico:
    """Frases, termos isolados e leis por tópico (uso interno).

    Prontos para casar contra o texto normalizado de um item.
    """

    def __init__(
        self,
        frases_media: list[tuple[str, list[str]]],
        termos_isolados: list[tuple[str, list[str]]],
        leis: list[tuple[str, list[str]]],
    ) -> None:
        self.frases_media = frases_media
        self.termos_isolados = termos_isolados
        self.leis = leis


def _construir_lexico(vocabulario: list[TopicoVocabulario]) -> _Lexico:
    """Monta o léxico (frases, termos isolados e leis) de cada tópico do vocabulário recebido."""
    frases_media: list[tuple[str, list[str]]] = []
    termos_isolados: list[tuple[str, list[str]]] = []
    for topico in vocabulario:
        frases, isolados = _termos_do_topico(topico.texto_original)
        frases_media.append((topico.slug, frases))
        termos_isolados.append((topico.slug, isolados))
    leis = [(t.slug, _leis_do_topico(t.texto_original)) for t in vocabulario]
    return _Lexico(frases_media=frases_media, termos_isolados=termos_isolados, leis=leis)


def _melhor_casamento(
    normalizado: str, termos_por_topico: list[tuple[str, list[str]]]
) -> tuple[str, str] | None:
    """O `(slug, termo)` mais longo entre os que aparecem em `normalizado`, ou `None`."""
    melhor: tuple[str, str] | None = None
    for slug, termos in termos_por_topico:
        for termo in termos:
            if termo and termo in normalizado and (melhor is None or len(termo) > len(melhor[1])):
                melhor = (slug, termo)
    return melhor


def _classificar_um(item: ItemParaClassificar, lexico: _Lexico) -> Classificacao:
    """Classifica um item pelo léxico.

    Ordem: lei citada (alta) > frase de 2+ palavras mais específica (media) > termo isolado, que
    não basta sozinho (baixa, sem tópico) > nada (baixa, sem correspondência).
    """
    texto = f"{item.comando or ''} {item.enunciado}"
    normalizado = _normalizar(texto)
    citadas = _leis_no_texto(texto)
    for slug, leis_do_topico in lexico.leis:
        achada = next((lei for lei in leis_do_topico if lei in citadas), None)
        if achada is not None:
            return Classificacao(
                numero_item=item.numero_item,
                topico_slug=slug,
                confianca="alta",
                evidencia=f"cita a Lei nº {achada}, do tópico",
                origem="regras",
            )
    melhor_frase = _melhor_casamento(normalizado, lexico.frases_media)
    if melhor_frase is not None:
        slug_melhor, frase_melhor = melhor_frase
        return Classificacao(
            numero_item=item.numero_item,
            topico_slug=slug_melhor,
            confianca="media",
            evidencia=f'contém o termo "{frase_melhor}" do tópico',
            origem="regras",
        )
    melhor_isolado = _melhor_casamento(normalizado, lexico.termos_isolados)
    if melhor_isolado is not None:
        slug_isolado, termo_isolado = melhor_isolado
        return Classificacao(
            numero_item=item.numero_item,
            topico_slug=None,
            confianca="baixa",
            evidencia=_TERMO_ISOLADO_NAO_BASTA.format(termo=termo_isolado, slug=slug_isolado),
            origem="regras",
        )
    return Classificacao(
        numero_item=item.numero_item,
        topico_slug=None,
        confianca="baixa",
        evidencia=SEM_CORRESPONDENCIA,
        origem="regras",
    )


def classificar_por_regras(
    itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]
) -> list[Classificacao]:
    """Classifica cada item só com o léxico determinístico (sem modelo).

    Args:
        itens: os itens a classificar.
        vocabulario: os tópicos do conteúdo programático do edital.

    Returns:
        Uma `Classificacao` (`origem="regras"`, `motivo_fallback=None`) por item, na ordem de
        `itens`.
    """
    lexico = _construir_lexico(vocabulario)
    return [_classificar_um(item, lexico) for item in itens]


class ClassificadorPorRegras:
    """Implementação determinística da porta: `classificar_por_regras`, sem modelo."""

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]
    ) -> tuple[list[Classificacao], MotivosRejeicao]:
        """Classifica o lote inteiro só com o léxico (ver `classificar_por_regras`).

        Nunca rejeita nada — o léxico sempre decide algo (mesmo que `"baixa"`/sem
        correspondência) — então `motivos_rejeicao` vem sempre vazio.
        """
        return classificar_por_regras(itens, vocabulario), {}


# --- Orquestração (IA em lote, com fallback por regras) -----------------------------------


def _por_regras_com_motivo(
    itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario], motivo: str | None
) -> ResultadoClassificacao:
    """`classificar_por_regras` com `motivo_fallback` uniforme (sem IA disponível, ou erro nela)."""
    classificacoes = [
        c.model_copy(update={"motivo_fallback": motivo})
        for c in classificar_por_regras(itens, vocabulario)
    ]
    return ResultadoClassificacao(classificacoes=classificacoes)


async def _classificar_um_lote(
    itens: list[ItemParaClassificar],
    vocabulario: list[TopicoVocabulario],
    classificador_ia: ClassificadorDeTopico,
) -> list[Classificacao]:
    """Classifica um único lote (já do tamanho de `config.lote_classificacao`) pela IA.

    Cada item que a IA não decidiu com sucesso (chamada inteira que falhou, entrada rejeitada
    por `interpretar_resposta`, ou item que ela simplesmente não devolveu) cai para regras —
    nunca o lote inteiro por causa de um item só, exceto quando a chamada em si falhou (aí não
    há nenhuma resposta aproveitável de jeito nenhum).
    """
    try:
        recebidas, motivos_rejeicao = await classificador_ia.classificar_lote(itens, vocabulario)
    except Exception as erro:  # noqa: BLE001 — deliberado: qualquer falha do provedor (rede,
        # cota, resposta que nem é JSON) degrada para regras — arquitetura §8, "nunca bloquear".
        # Só o tipo vai para o motivo, para não vazar detalhe do provedor.
        motivo = f"erro na IA: {type(erro).__name__}"
        return [
            c.model_copy(update={"motivo_fallback": motivo})
            for c in classificar_por_regras(itens, vocabulario)
        ]

    por_numero = {c.numero_item: c for c in recebidas}
    regras_fallback: dict[int, Classificacao] | None = None
    resultado: list[Classificacao] = []
    for item in itens:
        recebida = por_numero.get(item.numero_item)
        if recebida is not None:
            resultado.append(recebida)
            continue
        if regras_fallback is None:
            regras_fallback = {c.numero_item: c for c in classificar_por_regras(itens, vocabulario)}
        motivo = motivos_rejeicao.get(item.numero_item, ITEM_AUSENTE)
        resultado.append(
            regras_fallback[item.numero_item].model_copy(update={"motivo_fallback": motivo})
        )
    return resultado


async def classificar(
    itens: list[ItemParaClassificar],
    vocabulario: list[TopicoVocabulario],
    classificador_ia: ClassificadorDeTopico | None,
    motivo_sem_ia: str | None,
    tamanho_lote: int,
) -> ResultadoClassificacao:
    """Classifica todos os itens em lotes de `tamanho_lote`, pela IA quando há uma.

    Fatia `itens` com `montar_lotes` e chama `classificador_ia` uma vez por lote — é assim que
    o teto diário de custo se mantém (um caderno de 70 itens com lote de 20 faz 4 chamadas, não
    70). Mesmo desenho de `agentes.analista_de_edital.gerar_dna`: nunca levanta por falha do
    provedor.

    Args:
        itens: todos os itens a classificar (ex.: os itens de um caderno inteiro).
        vocabulario: os tópicos do conteúdo programático do edital.
        classificador_ia: implementação da porta com modelo, ou `None` (sem chave / teto
            atingido).
        motivo_sem_ia: motivo registrado quando `classificador_ia` é `None`.
        tamanho_lote: quantos itens vão em cada chamada à IA (`config.lote_classificacao`);
            ignorado quando `classificador_ia` é `None` (regras não precisa de lote).

    Returns:
        `ResultadoClassificacao` com uma `Classificacao` por item, na ordem de `itens`; nunca
        levanta por falha do modelo.
    """
    if not itens:
        return ResultadoClassificacao(classificacoes=[])
    if classificador_ia is None:
        return _por_regras_com_motivo(itens, vocabulario, motivo_sem_ia)

    resultado: list[Classificacao] = []
    inicio = 0
    for tamanho in montar_lotes(len(itens), tamanho_lote):
        lote = itens[inicio : inicio + tamanho]
        resultado.extend(await _classificar_um_lote(lote, vocabulario, classificador_ia))
        inicio += tamanho
    return ResultadoClassificacao(classificacoes=resultado)
