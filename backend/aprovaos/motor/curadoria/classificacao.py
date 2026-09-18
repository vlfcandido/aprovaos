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

import re
import unicodedata
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, TypeAdapter, ValidationError

Confianca = Literal["alta", "media", "baixa"]

#: Evidência fixa quando nenhum termo do léxico nem lei citada casa com o item (contrato da
#: skill `ingestao-de-provas`).
SEM_CORRESPONDENCIA = "sem correspondência no vocabulário"

#: Motivo de fallback quando a IA classificou o lote mas não devolveu entrada para um item.
ITEM_AUSENTE = "item ausente na resposta do modelo"

_CERCA_DE_CODIGO = re.compile(r"\A```[a-zA-Z]*\s*\n?(.*?)\n?```\Z", re.DOTALL)


class ClassificacaoInvalida(ValueError):
    """A resposta da IA não tem a forma esperada ou cita um `topico_slug` fora do vocabulário.

    Levantada por `interpretar_resposta`; nunca escapa até o aluno — `classificar` a converte em
    fallback por regras para o lote (mesmo espírito de `gerar_dna`: uma resposta que descumpre o
    contrato vale tanto quanto uma chamada que falhou).
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


@runtime_checkable
class ClassificadorDeTopico(Protocol):
    """Porta do classificador.

    Recebe o lote e o vocabulário e devolve uma classificação por item.
    """

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]
    ) -> list[Classificacao]:
        """Classifica todo o lote de uma vez.

        Args:
            itens: os itens do lote (até `config.lote_classificacao`).
            vocabulario: os tópicos do conteúdo programático do edital.

        Returns:
            Uma `Classificacao` por item que a implementação conseguiu decidir; um item ausente
            na lista devolvida é tratado por quem chama como "sem resposta para ele".
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


def interpretar_resposta(texto: str, slugs_validos: set[str]) -> list[Classificacao]:
    """Converte a resposta do lote (JSON) em `Classificacao`, uma por entrada devolvida.

    Args:
        texto: resposta bruta do modelo (JSON, possivelmente entre cerca de código).
        slugs_validos: os slugs do vocabulário enviado no lote — nenhum `topico_slug` fora
            disso é aceito.

    Returns:
        Uma `Classificacao` (`origem="ia"`) por entrada da resposta, na ordem em que vieram.
        Pode ter menos itens do que o lote pedido — quem chama (`classificar`) decide o que
        fazer com os que faltaram.

    Raises:
        ClassificacaoInvalida: o JSON não tem a forma esperada, ou alguma entrada cita um
            `topico_slug` que não está em `slugs_validos` (o modelo inventou um tópico).
    """
    limpo = texto.strip()
    cercado = _CERCA_DE_CODIGO.match(limpo)
    if cercado is not None:
        limpo = cercado.group(1).strip()
    try:
        entradas = TypeAdapter(list[_EntradaBruta]).validate_json(limpo)
    except ValidationError as erro:
        raise ClassificacaoInvalida(f"resposta fora do contrato: {erro}") from erro
    resultado: list[Classificacao] = []
    for entrada in entradas:
        if entrada.topico_slug is not None and entrada.topico_slug not in slugs_validos:
            raise ClassificacaoInvalida(f"slug fora do vocabulário: {entrada.topico_slug}")
        resultado.append(
            Classificacao(
                numero_item=entrada.numero_item,
                topico_slug=entrada.topico_slug,
                confianca=entrada.confianca,
                evidencia=entrada.evidencia,
                origem="ia",
            )
        )
    return resultado


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


def _frases_do_topico(texto_original: str) -> list[str]:
    """As frases do léxico de um tópico: o núcleo do `texto_original`, partido em candidatos.

    O núcleo é o texto sem o número do item, sem parênteses (citações de artigo) e só até o
    primeiro `:`/`—` (o que vem depois costuma ser a lista de subitens, não o nome do tópico).
    Cada candidato (separado por vírgula ou por " e ") vira uma frase do léxico, normalizada,
    desde que tenha pelo menos uma palavra fora da lista de conectivos — palavra isolada só
    entra se tiver 6 letras ou mais (evita termo genérico demais, tipo "poder").
    """
    sem_numero = _PREFIXO_NUMERO.sub("", texto_original).strip()
    marcadores = [m for m in _ENRIQUECIMENTO_POR_MARCADOR if m in sem_numero.lower()]
    sem_parenteses = _PARENTESES.sub("", sem_numero)
    nucleo = _SEPARADOR_DE_NUCLEO.split(sem_parenteses, maxsplit=1)[0]
    frases: list[str] = []
    for candidato in _SEPARADOR_DE_CANDIDATO.split(nucleo):
        normalizado = _normalizar(candidato).strip(" .")
        if not normalizado:
            continue
        palavras = normalizado.split()
        significativas = [p for p in palavras if p not in _STOPWORDS]
        if not significativas:
            continue
        if len(significativas) == 1 and len(significativas[0]) < 6:
            continue
        frases.append(normalizado)
    for marcador in marcadores:
        frases.extend(_ENRIQUECIMENTO_POR_MARCADOR[marcador])
    return frases


def _leis_do_topico(texto_original: str) -> list[str]:
    """As leis citadas no `texto_original` de um tópico, normalizadas como `"X/AAAA"`."""
    return sorted(_leis_no_texto(texto_original))


class _Lexico:
    """Termos e leis por tópico, prontos para casar contra o texto de um item (uso interno)."""

    def __init__(
        self, termos: list[tuple[str, list[str]]], leis: list[tuple[str, list[str]]]
    ) -> None:
        self.termos = termos
        self.leis = leis


def _construir_lexico(vocabulario: list[TopicoVocabulario]) -> _Lexico:
    """Monta o léxico (termos e leis) de cada tópico do vocabulário recebido."""
    termos = [(t.slug, _frases_do_topico(t.texto_original)) for t in vocabulario]
    leis = [(t.slug, _leis_do_topico(t.texto_original)) for t in vocabulario]
    return _Lexico(termos=termos, leis=leis)


def _classificar_um(item: ItemParaClassificar, lexico: _Lexico) -> Classificacao:
    """Classifica um item pelo léxico: lei citada (alta) > termo mais específico (media) > nada."""
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
    melhor: tuple[str, str] | None = None
    for slug, frases in lexico.termos:
        for frase in frases:
            if frase and frase in normalizado:
                if melhor is None or len(frase) > len(melhor[1]):
                    melhor = (slug, frase)
    if melhor is not None:
        slug_melhor, frase_melhor = melhor
        return Classificacao(
            numero_item=item.numero_item,
            topico_slug=slug_melhor,
            confianca="media",
            evidencia=f'contém o termo "{frase_melhor}" do tópico',
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
    ) -> list[Classificacao]:
        """Classifica o lote inteiro só com o léxico (ver `classificar_por_regras`)."""
        return classificar_por_regras(itens, vocabulario)


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


async def classificar(
    itens: list[ItemParaClassificar],
    vocabulario: list[TopicoVocabulario],
    classificador_ia: ClassificadorDeTopico | None,
    motivo_sem_ia: str | None,
) -> ResultadoClassificacao:
    """Classifica um lote pela IA quando há uma; cai para regras onde ela não decidiu.

    Mesmo desenho de `agentes.analista_de_edital.gerar_dna`: nunca levanta por falha do
    provedor — uma chamada que falhou vira regras para o lote inteiro; uma resposta que veio mas
    não cobriu um item (ausente ou com `topico_slug` inventado, que `interpretar_resposta` já
    rejeitou) vira regras só para aquele item, preservando os que a IA decidiu certo.

    Args:
        itens: os itens do lote.
        vocabulario: os tópicos do conteúdo programático do edital.
        classificador_ia: implementação da porta com modelo, ou `None` (sem chave / teto
            atingido).
        motivo_sem_ia: motivo registrado quando `classificador_ia` é `None`.

    Returns:
        `ResultadoClassificacao` com uma `Classificacao` por item; nunca levanta por falha do
        modelo.
    """
    if classificador_ia is None:
        return _por_regras_com_motivo(itens, vocabulario, motivo_sem_ia)
    try:
        recebidas = await classificador_ia.classificar_lote(itens, vocabulario)
    except Exception as erro:  # noqa: BLE001 — deliberado: qualquer falha do provedor (rede,
        # cota, resposta fora do esquema) degrada para regras — arquitetura §8, "nunca bloquear".
        # Só o tipo vai para o motivo, para não vazar detalhe do provedor.
        motivo = f"erro na IA: {type(erro).__name__}"
        return _por_regras_com_motivo(itens, vocabulario, motivo)

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
        resultado.append(
            regras_fallback[item.numero_item].model_copy(update={"motivo_fallback": ITEM_AUSENTE})
        )
    return ResultadoClassificacao(classificacoes=resultado)
