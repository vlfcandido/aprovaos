"""Extrator de dispositivo legal a partir do HTML compilado do Planalto (fundação jurídica).

O que é: `extrair_artigo(html, numero)`, função pura que recebe o HTML "texto compilado" que o
Planalto publica para uma norma (CF/1988, leis ordinárias etc.) e devolve o artigo pedido —
caput, incisos e parágrafos, cada um com o texto literal **vigente** e a procedência da redação
("Redação dada pela Emenda Constitucional nº 19, de 1998", "Incluído pela...", "Vide Decreto
nº...") quando o Planalto a informa. Não abre rede, não conhece banco, não sabe o que é uma
`Aula` ou uma `Questao` — só interpreta o HTML.

O ponto delicado (e o motivo deste módulo existir): o Planalto mostra, lado a lado, o texto
**revogado** (dentro de uma tag `<strike>`) e o texto **vigente** (fora dela) — às vezes vários
textos revogados em sequência, de emendas diferentes, até chegar ao vigente. Confundir os dois
serviria ao aluno um dispositivo que não existe mais, o que é pior do que não servir nada. A
estratégia adotada é **remover todo o conteúdo de `<strike>...</strike>` antes de qualquer outra
coisa** (medido: nunca aninhado nos dois HTMLs de fixture desta tarefa — ver
`.superpowers/sdd/V3b-multipla-escolha/juridico-passo-1-report.md`) e só então segmentar por
parágrafo e classificar pelo texto visível (não pelo atributo `name=` das âncoras internas do
Planalto, que se mostrou inconsistente entre versões revogadas e vigentes do mesmo dispositivo —
ex.: `art37xi`, `art37xi.` e `art37xi..` coexistem para três redações diferentes do mesmo inciso).

Escopo desta rodada (documentado para não ser confundido com limitação escondida): o extrator
devolve caput, incisos (`I`, `II`, ...) e parágrafos (`§ 1º`, ...), inclusive incisos aninhados
dentro de um parágrafo (ex.: CF art. 37, § 3º, I a III). **Alíneas** (`a)`, `b)`, `c)`) são
capturadas como filhas do inciso/parágrafo mais próximo, cada uma com sua própria procedência de
redação — mas a tabela `dispositivo_legal` (`docs/04-modelo-de-dados.md` §3) não tem coluna para
esse nível; decidir como uma alínea vira uma linha dessa tabela fica para quando alguém precisar
citar uma alínea especificamente (registrado no relatório desta rodada, não decidido aqui).

Quando ler: antes de mudar como uma citação de aula/questão resolve para o texto de lei; ao
investigar por que um trecho citado não bate com o que o Planalto publica.
"""

import html as _html_stdlib
import re
from typing import Literal

from pydantic import BaseModel, Field

from aprovaos.dominio.erros import DispositivoNaoEncontrado, EstruturaNaoTratada

TipoTrecho = Literal["caput", "inciso", "paragrafo", "alinea"]


class TrechoDispositivo(BaseModel):
    """Um trecho do artigo (caput, inciso, parágrafo ou alínea), com o texto literal vigente.

    Attributes:
        tipo: nível do trecho na hierarquia do artigo.
        identificador: o rótulo do trecho como a lei o numera (`"caput"`, `"I"`, `"§ 3º"`,
            `"a"`). Para uma alínea, é só a letra — o pai (`alineas` de quem a contém) já dá o
            contexto; não é preciso repetir "XVI, a" aqui.
        texto: texto literal do trecho, incluindo a própria numeração (ex.: `"I - os cargos,
            empregos..."`), exatamente como o Planalto publica a redação vigente — sem o texto
            revogado e sem a anotação de procedência (essa vai em `redacao_de`).
        redacao_de: a nota de procedência que o Planalto anexou a este trecho específico (ex.:
            `"Redação dada pela Emenda Constitucional nº 19, de 1998"`, `"Incluído pela Emenda
            Constitucional nº 109, de 2021"`, `"Vide Decreto nº 12.807, de 29/12/2025"`); `None`
            quando o Planalto não anexou nenhuma nota a este trecho (texto original da norma, ou
            nota indisponível nesta fonte).
        alineas: alíneas que pertencem a este trecho, na ordem em que aparecem; lista vazia
            quando não há.
    """

    tipo: TipoTrecho
    identificador: str
    texto: str
    redacao_de: str | None
    alineas: list["TrechoDispositivo"] = Field(default_factory=list)


class ArtigoExtraido(BaseModel):
    """O artigo pedido, decomposto em caput + incisos + parágrafos, todos vigentes.

    Attributes:
        numero: o número do artigo como foi pedido (ex.: `"37"`, `"6"`) — sem o `"Art."` nem o
            `"º"`.
        caput: o caput do artigo.
        incisos: incisos do caput, na ordem em que aparecem — não os de um parágrafo específico
            (esses entram em `paragrafos[i].alineas`, junto com as alíneas de fato; o campo
            `alineas` de `TrechoDispositivo` é o único lugar de filhos que este modelo tem nesta
            rodada, então acolhe tanto incisos-de-parágrafo quanto alíneas — o `tipo` de cada
            filho, `"inciso"` ou `"alinea"`, preserva a distinção real).
        paragrafos: parágrafos do artigo, na ordem em que aparecem; cada um com seus próprios
            incisos/alíneas em `paragrafos[i].alineas`, quando houver.
    """

    numero: str
    caput: TrechoDispositivo
    incisos: list[TrechoDispositivo] = Field(default_factory=list)
    paragrafos: list[TrechoDispositivo] = Field(default_factory=list)


_PADRAO_STRIKE = re.compile(r"<strike\b[^>]*>.*?</strike\s*>", re.IGNORECASE | re.DOTALL)
_PADRAO_PARAGRAFO_HTML = re.compile(r"<p\b[^>]*>(.*?)</p\s*>", re.IGNORECASE | re.DOTALL)
_PADRAO_TAG = re.compile(r"<[^>]+>")
_PADRAO_ESPACOS = re.compile(r"\s+")
_PADRAO_ANOTACAO = re.compile(
    r"\(\s*(?:Reda[cç][aã]o dada|Inclu[ií]d[oa]|Acrescid[oa]|Renumerad[oa]|Revogad[oa]|"
    r"Suprimid[oa]|Vide|Vig[eê]ncia)[^()]*\)",
    re.IGNORECASE,
)
# O Planalto também encadeia, depois de uma ou mais notas "(Vide Decreto/Lei nº..., de ANO)",
# um link cujo texto é só "Vigência" — sem parênteses (medido em `lei14133_planalto_compilada
# .htm`, art. 6º, XXII: cadeia de decretos regulamentadores sucessivos). Maiúscula e sem
# parênteses é o que distingue esse marcador da palavra comum "vigência" em minúsculo, que
# aparece dezenas de vezes em frases de verdade (ex.: "a data de vigência desta Lei") e não pode
# ser removida — por isso este padrão é sensível a maiúscula/minúscula (sem `re.IGNORECASE`).
_PADRAO_VIGENCIA_SEM_PARENTESES = re.compile(r"\bVig[eê]ncia\b")
_NUMERO_ARTIGO_COM_MILHAR = r"\d{1,3}(?:\.\d{3})*"
"""Um número de artigo como o Planalto grafa, inclusive com ponto de milhar a partir de 1.000
(medido: `lei13105_planalto_compilada.htm` — CPC/2015 — escreve `"Art. 1.009."`, nunca `"Art.
1009."`; sem isso, `_PADRAO_INICIO_ARTIGO_QUALQUER` não reconhece o início de um artigo de 4
dígitos como fronteira, e `_padrao_caput` não o acha de jeito nenhum)."""
_PADRAO_INICIO_ARTIGO_QUALQUER = re.compile(rf"^Art\.\s*{_NUMERO_ARTIGO_COM_MILHAR}[ºo]?\.?(?!\d)")
_PADRAO_PARAGRAFO = re.compile(r"^(§\s*\d+[ºo]?\.?|Par[aá]grafo único\.?)\s")
_PADRAO_INCISO = re.compile(r"^([IVXLCDM]+)\s*[-–]\s")
_PADRAO_ALINEA = re.compile(r"^([a-z])\)\s")


def _eh_titulo_estrutural(texto: str) -> bool:
    """Reconhece um título de divisão do diploma (capítulo, título, seção...), não um dispositivo.

    O Planalto intercala, entre o fim de um artigo e o caput do próximo, parágrafos como
    "CAPÍTULO IV" / "DOS AGENTES PÚBLICOS" (medido em `lei14133_planalto_compilada.htm`, entre
    os arts. 6º e 7º) — não fazem parte do texto de nenhum dos dois artigos. O heurístico é
    estrutural, não uma lista fixa de palavras: todo dispositivo de verdade (caput, inciso,
    parágrafo, alínea) tem letra minúscula em algum lugar; um título de divisão, não.

    Args:
        texto: o texto já limpo (sem tags, sem anotação) de um parágrafo.

    Returns:
        `True` quando o texto não tem nenhuma letra minúscula (e tem pelo menos uma letra).
    """
    return any(c.isalpha() for c in texto) and texto == texto.upper()


def _com_pontuacao_de_milhar(numero: str) -> str:
    """`"1009"` → `"1.009"`; `"37"` → `"37"` (sem alteração abaixo de 1.000).

    `extrair_artigo` sempre recebe o número normalizado, só dígitos (o mesmo formato que
    `dominio.citacao._normalizar_numero` produz de uma citação em texto) — mas o Planalto grafa
    artigos de 4+ dígitos com ponto de milhar (`"Art. 1.009."`). Esta função gera essa grafia
    para `_padrao_caput` tentar as duas formas; não afeta números com menos de 4 dígitos.
    """
    if len(numero) <= 3:
        return numero
    return f"{numero[:-3]}.{numero[-3:]}"


def _padrao_caput(numero: str) -> re.Pattern[str]:
    """Monta o padrão do caput do artigo `numero`.

    Ex.: `"Art. 37."`, `"Art. 6º"`, `"Art. 1.009."` — a última com o ponto de milhar do
    Planalto para números de 4+ dígitos (ver `_com_pontuacao_de_milhar`).
    """
    variantes = {numero, _com_pontuacao_de_milhar(numero)}
    alternativas = "|".join(re.escape(variante) for variante in variantes)
    return re.compile(rf"^Art\.\s*(?:{alternativas})[ºo]?\.?(?!\d)\s")


def _texto_do_paragrafo(bloco_html: str) -> tuple[str, str | None] | None:
    """Extrai o texto literal e a nota de procedência de um bloco `<p>...</p>` já sem `<strike>`.

    Args:
        bloco_html: o conteúdo interno de um `<p>` (sem as tags `<p>`/`</p>`), com todo o
            conteúdo de `<strike>` já removido pelo chamador.

    Returns:
        `(texto, redacao_de)` com espaços normalizados, ou `None` quando o bloco não sobra texto
        nenhum depois de remover as tags — o caso normal de um parágrafo que era só texto
        revogado.
    """
    sem_tags = _PADRAO_TAG.sub(" ", bloco_html)
    texto_bruto = _html_stdlib.unescape(sem_tags)
    anotacoes = [m.group(0) for m in _PADRAO_ANOTACAO.finditer(texto_bruto)]
    anotacoes += [m.group(0) for m in _PADRAO_VIGENCIA_SEM_PARENTESES.finditer(texto_bruto)]
    sem_anotacao = _PADRAO_ANOTACAO.sub(" ", texto_bruto)
    sem_anotacao = _PADRAO_VIGENCIA_SEM_PARENTESES.sub(" ", sem_anotacao)
    texto = _PADRAO_ESPACOS.sub(" ", sem_anotacao).strip()
    if not texto:
        return None
    redacao_de = "; ".join(_PADRAO_ESPACOS.sub(" ", a).strip("() ").strip() for a in anotacoes)
    return texto, (redacao_de or None)


def _paragrafos_vigentes(html: str) -> list[tuple[str, str | None]]:
    """Devolve, em ordem, o texto e a procedência de cada `<p>` com conteúdo vigente.

    Remove primeiro todo `<strike>...</strike>` (texto revogado, nunca aninhado nos HTMLs desta
    fonte); parágrafos que ficam vazios depois disso (eram só texto revogado) são descartados.

    Args:
        html: o HTML compilado inteiro (ou um trecho dele).

    Returns:
        Lista de `(texto, redacao_de)`, na ordem do documento.
    """
    sem_revogado = _PADRAO_STRIKE.sub("", html)
    resultado: list[tuple[str, str | None]] = []
    for bloco in _PADRAO_PARAGRAFO_HTML.findall(sem_revogado):
        item = _texto_do_paragrafo(bloco)
        if item is not None:
            resultado.append(item)
    return resultado


def extrair_artigo(html: str, numero: str) -> ArtigoExtraido:
    """Extrai o artigo `numero` do HTML compilado do Planalto, só com texto vigente.

    Args:
        html: o HTML "texto compilado" da norma (já decodificado como `str`).
        numero: o número do artigo, sem `"Art."` nem `"º"` (ex.: `"37"`, `"6"`).

    Returns:
        O artigo decomposto em caput, incisos e parágrafos vigentes, cada um com a procedência
        de redação que o Planalto informou.

    Raises:
        DispositivoNaoEncontrado: nenhum parágrafo do HTML começa com `"Art. {numero}"` vigente.
        EstruturaNaoTratada: uma alínea aparece sem inciso/parágrafo/caput anterior a que
            pertencer — a função para em vez de inventar a hierarquia.
    """
    paragrafos = _paragrafos_vigentes(html)
    padrao_caput = _padrao_caput(numero)

    inicio = next((i for i, (texto, _) in enumerate(paragrafos) if padrao_caput.match(texto)), None)
    if inicio is None:
        raise DispositivoNaoEncontrado(
            f"Nenhum parágrafo vigente começa com 'Art. {numero}' neste HTML."
        )

    fim = next(
        (
            i
            for i in range(inicio + 1, len(paragrafos))
            if _PADRAO_INICIO_ARTIGO_QUALQUER.match(paragrafos[i][0])
        ),
        len(paragrafos),
    )

    texto_caput, redacao_caput = paragrafos[inicio]
    caput = TrechoDispositivo(
        tipo="caput", identificador="caput", texto=texto_caput, redacao_de=redacao_caput
    )
    incisos: list[TrechoDispositivo] = []
    paragrafos_do_artigo: list[TrechoDispositivo] = []
    contexto_incisos: list[TrechoDispositivo] = incisos
    alvo_alinea: TrechoDispositivo | None = None

    for texto, redacao in paragrafos[inicio + 1 : fim]:
        if _eh_titulo_estrutural(texto):
            continue  # título de capítulo/seção entre este artigo e o próximo, não é dispositivo

        m_paragrafo = _PADRAO_PARAGRAFO.match(texto)
        m_inciso = _PADRAO_INCISO.match(texto)
        m_alinea = _PADRAO_ALINEA.match(texto)

        if m_paragrafo is not None:
            item = TrechoDispositivo(
                tipo="paragrafo",
                identificador=m_paragrafo.group(1),
                texto=texto,
                redacao_de=redacao,
            )
            paragrafos_do_artigo.append(item)
            contexto_incisos = item.alineas  # incisos após este § pertencem a ele
            alvo_alinea = item
        elif m_inciso is not None:
            item = TrechoDispositivo(
                tipo="inciso", identificador=m_inciso.group(1), texto=texto, redacao_de=redacao
            )
            contexto_incisos.append(item)
            alvo_alinea = item
        elif m_alinea is not None:
            if alvo_alinea is None:
                raise EstruturaNaoTratada(
                    f"Alínea sem inciso/parágrafo anterior a que pertencer: {texto!r}"
                )
            alvo_alinea.alineas.append(
                TrechoDispositivo(
                    tipo="alinea",
                    identificador=m_alinea.group(1),
                    texto=texto,
                    redacao_de=redacao,
                )
            )
        else:
            raise EstruturaNaoTratada(
                f"Parágrafo vigente sem forma reconhecida (nem §, nem inciso, nem alínea): "
                f"{texto!r}"
            )

    return ArtigoExtraido(
        numero=numero, caput=caput, incisos=incisos, paragrafos=paragrafos_do_artigo
    )


_PADRAO_SO_DIGITOS = re.compile(r"\D+")


def _numero_do_identificador(identificador: str) -> str:
    """`"§ 3º"` / `"§ 10."` → `"3"` / `"10"` — só os dígitos, para comparar com uma citação.

    O identificador de parágrafo que `extrair_artigo` produz carrega a pontuação exata do
    Planalto (`"º"` para 1º-9º, só `"."` a partir do 10º — achado real do HTML da CF); uma
    citação (`dominio.citacao.ReferenciaLegal.paragrafo`) já chega normalizada para só dígitos.
    Comparar por número evita depender dessa pontuação inconsistente da fonte.
    """
    return _PADRAO_SO_DIGITOS.sub("", identificador)


def localizar_trecho(
    artigo: ArtigoExtraido, *, inciso: str | None = None, paragrafo: str | None = None
) -> TrechoDispositivo:
    """Localiza, dentro de um artigo já extraído, o trecho exato que uma citação aponta.

    É o elo entre `dominio.citacao.extrair_citacoes` (que só sabe ler o texto de uma questão) e
    o artigo de verdade: dada a `ArtigoExtraido` (de `extrair_artigo`) e o `inciso`/`paragrafo`
    de uma `ReferenciaLegal`, devolve o `TrechoDispositivo` correspondente — nunca inventa um
    trecho que a citação não pediu.

    Args:
        artigo: o artigo já extraído (`extrair_artigo`).
        inciso: identificador do inciso citado (ex.: `"II"`), em algarismos romanos; `None`
            quando a citação não desce a esse nível.
        paragrafo: número do parágrafo citado (só dígitos, ex.: `"3"`, `"10"` — o mesmo formato
            que `dominio.citacao.ReferenciaLegal.paragrafo` produz); `None` quando a citação é do
            caput ou não desce a esse nível.

    Returns:
        `artigo.caput` quando nem `inciso` nem `paragrafo` são dados (citação simples ao
        artigo, ex.: `"art. 37 da CF"`, equivalente a `"art. 37, caput, da CF"`); o parágrafo
        (ou o inciso dentro dele, quando os dois são dados) quando `paragrafo` é dado; o inciso
        do caput quando só `inciso` é dado.

    Raises:
        DispositivoNaoEncontrado: o `inciso`/`paragrafo` pedido não existe neste artigo — nunca
            devolve o caput como aproximação.
    """
    if paragrafo is not None:
        encontrado_paragrafo = next(
            (
                p
                for p in artigo.paragrafos
                if _numero_do_identificador(p.identificador) == paragrafo
            ),
            None,
        )
        if encontrado_paragrafo is None:
            raise DispositivoNaoEncontrado(f"§ {paragrafo} não encontrado no art. {artigo.numero}")
        if inciso is None:
            return encontrado_paragrafo
        encontrado_inciso = next(
            (i for i in encontrado_paragrafo.alineas if i.identificador == inciso), None
        )
        if encontrado_inciso is None:
            raise DispositivoNaoEncontrado(
                f"inciso {inciso} não encontrado no § {paragrafo} do art. {artigo.numero}"
            )
        return encontrado_inciso

    if inciso is not None:
        encontrado_inciso = next((i for i in artigo.incisos if i.identificador == inciso), None)
        if encontrado_inciso is None:
            raise DispositivoNaoEncontrado(
                f"inciso {inciso} não encontrado no art. {artigo.numero}"
            )
        return encontrado_inciso

    return artigo.caput
