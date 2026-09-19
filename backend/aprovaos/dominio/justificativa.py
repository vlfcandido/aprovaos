"""Contrato e validador mecânico da justificativa de questão, ancorada em dispositivo legal.

O que é: o modelo de entrada que o agente `gerador-de-justificativa` recebe
(`DispositivoParaJustificar`, `AlternativaParaJustificar`, `QuestaoParaJustificar`), o que ele
devolve (`Afirmacao`, `JustificativaCertoErrado`, `JustificativaMultiplaEscolha`) e
`verificar_justificativa_certo_errado`/`verificar_justificativa_multipla_escolha` — o validador
**mecânico**, sem LLM, que decide se uma justificativa pode ser gravada. Nenhuma chamada de
rede, banco ou modelo acontece aqui; só comparação de texto.

**A regra de ouro deste passo** (decisão do dono, ver o pedido da tarefa): toda justificativa
cita um dispositivo que está entre os oferecidos (os que já estão ligados àquela questão em
`citacao`) e o trecho citado existe **literalmente** — como substring — no texto vigente daquele
dispositivo. Zero invenção de fonte: o gerador só pode citar o que recebeu; o validador reprova
qualquer citação fora disso. Reprovou, não grava — melhor faltar do que mentir.

A comparação do dispositivo citado contra os oferecidos passa por
`dominio.citacao.normalizar_citacao_para_comparacao` dos dois lados: ordinal, "o" e ponto final
não mudam a identidade do dispositivo (`"art. 1º"` do modelo é o mesmo `"art. 1"` gravado) — só o
número importa.

Quando ler: antes de mudar o prompt do `gerador-de-justificativa`; ao investigar por que uma
justificativa boa (ou ruim) foi aprovada/reprovada.
"""

import re

from pydantic import BaseModel, Field

from aprovaos.dominio.citacao import normalizar_citacao_para_comparacao


class DispositivoParaJustificar(BaseModel):
    """Um dispositivo já ligado à questão, oferecido ao gerador como única fonte permitida.

    Attributes:
        citacao_canonica: identificador único do dispositivo (`DispositivoLegal.citacao_canonica`,
            ex.: `"Lei 8.429/1992 art. 1º"`).
        texto: texto literal vigente do dispositivo — o que o validador usa para conferir se o
            `trecho_que_decide` de cada afirmação existe de fato.
    """

    citacao_canonica: str
    texto: str


class AlternativaParaJustificar(BaseModel):
    """Uma alternativa (A–E) de múltipla escolha, para o gerador ver o texto de todas.

    Attributes:
        letra: A–E.
        texto: o texto da alternativa.
        correta: se esta é a alternativa do gabarito.
    """

    letra: str
    texto: str
    correta: bool


class QuestaoParaJustificar(BaseModel):
    """O que o `gerador-de-justificativa` recebe para produzir a justificativa de uma questão.

    Attributes:
        tipo_item: `"certo_errado"` ou `"multipla_escolha"` — decide qual dos dois contratos de
            saída (`JustificativaCertoErrado`/`JustificativaMultiplaEscolha`) é esperado.
        comando: a instrução de julgamento do item, quando existir.
        texto_apoio: texto de apoio do item (situação hipotética), quando existir.
        enunciado: a afirmação a julgar (`certo_errado`) ou o enunciado da questão
            (`multipla_escolha`).
        gabarito: `"C"`/`"E"` para `certo_errado`; `None` para `multipla_escolha` (a correção já
            está em `alternativas[i].correta`).
        alternativas: as cinco alternativas, só para `multipla_escolha`; `None` para
            `certo_errado`.
        dispositivos: os dispositivos já ligados a esta questão — a única fonte que o gerador
            pode citar.
    """

    tipo_item: str
    comando: str | None
    texto_apoio: str | None
    enunciado: str
    gabarito: str | None
    alternativas: list[AlternativaParaJustificar] | None
    dispositivos: list[DispositivoParaJustificar]


class Afirmacao(BaseModel):
    """Uma frase da justificativa, apoiada em um dispositivo e no trecho literal que a decide.

    Attributes:
        texto: a frase que o aluno lê.
        dispositivo: `citacao_canonica` do dispositivo que sustenta a frase — tem de estar entre
            os `DispositivoParaJustificar` oferecidos ao gerador para esta questão.
        trecho_que_decide: o trecho literal do dispositivo que decide a frase — tem de existir,
            palavra por palavra (substring), no `texto` daquele dispositivo.
    """

    texto: str
    dispositivo: str
    trecho_que_decide: str


class JustificativaCertoErrado(BaseModel):
    """A saída do gerador para um item certo/errado — as duas obrigatórias.

    Attributes:
        afirmacoes_certo: por que o item estaria certo, apoiado na fonte.
        afirmacoes_errado: por que o item está errado, apoiado na fonte — presente mesmo quando
            o gabarito é "certo": o aluno vê os dois lados (contrato da skill
            `gerador-questao-banca`).
        cobertura_insuficiente: o gerador declara que os dispositivos ligados a esta questão
            **não cobrem** o assunto do item. `True` reprova a justificativa — ver
            `verificar_justificativa_certo_errado`.
    """

    afirmacoes_certo: list[Afirmacao]
    afirmacoes_errado: list[Afirmacao]
    cobertura_insuficiente: bool = False


class JustificativaPorAlternativa(BaseModel):
    """A justificativa de uma alternativa (A–E) — por que ela é, ou não é, a correta.

    Attributes:
        letra: A–E.
        afirmacoes: uma ou mais frases que sustentam a alternativa.
    """

    letra: str
    afirmacoes: list[Afirmacao]


class JustificativaMultiplaEscolha(BaseModel):
    """A saída do gerador para uma questão de múltipla escolha — as cinco obrigatórias.

    Attributes:
        alternativas: uma entrada por letra A–E, cada uma com as próprias afirmações.
    """

    alternativas: list[JustificativaPorAlternativa]


class Veredito(BaseModel):
    """O que o validador mecânico decide sobre uma justificativa.

    Attributes:
        aprovado: `True` só quando nenhum motivo de reprovação foi encontrado.
        motivos: os problemas achados, um por afirmação/regra violada; vazio quando `aprovado`.
    """

    aprovado: bool
    motivos: list[str] = Field(default_factory=list)


def _motivos_da_afirmacao(
    afirmacao: Afirmacao, dispositivos_por_citacao: dict[str, str], *, rotulo: str
) -> list[str]:
    """Os motivos de reprovação de uma única `Afirmacao` (lista vazia = afirmação válida)."""
    motivos: list[str] = []
    if not afirmacao.texto.strip():
        motivos.append(f"{rotulo}: afirmação sem texto")

    texto_dispositivo = dispositivos_por_citacao.get(
        normalizar_citacao_para_comparacao(afirmacao.dispositivo)
    )
    if texto_dispositivo is None:
        motivos.append(
            f"{rotulo}: dispositivo {afirmacao.dispositivo!r} não está entre os ligados à questão"
        )
        return motivos

    if not afirmacao.trecho_que_decide.strip():
        motivos.append(f"{rotulo}: trecho citado vazio")
    elif afirmacao.trecho_que_decide not in texto_dispositivo:
        motivos.append(
            f"{rotulo}: trecho citado não existe literalmente em {afirmacao.dispositivo!r}"
        )
    return motivos


def verificar_justificativa_certo_errado(
    justificativa: JustificativaCertoErrado,
    dispositivos: list[DispositivoParaJustificar],
) -> Veredito:
    """Valida mecanicamente uma `JustificativaCertoErrado`.

    Reprova quando: falta `afirmacoes_certo` ou `afirmacoes_errado` (as duas são obrigatórias —
    regra 3 da tarefa); alguma afirmação cita dispositivo fora dos `dispositivos` recebidos
    (regra 4 — zero invenção de fonte); o `trecho_que_decide` de alguma afirmação não existe
    literalmente no texto do dispositivo citado (regra 2); ou o gerador marcou
    `cobertura_insuficiente`.

    **Por que existe `cobertura_insuficiente`** (achado de 19/09/2026, lendo o `dev.db`): as três
    regras acima conferem **procedência** — "isso é verdade e vem da lei?" — e nenhuma confere
    **pertinência** — "isso é sobre a questão que ela acabou de responder?". Numa questão sobre
    legitimidade para propor ação de improbidade, o gerador entregou *"Se o item afirmasse que o
    sistema de responsabilização tutela a probidade na organização do Estado, estaria certo"*:
    citada, literal, verdadeira e sobre outra proposição. Acontece quando os dispositivos ligados
    ao tópico não cobrem o assunto daquele item — o gerador não tem do que falar e fala de outra
    coisa, sem violar nenhuma regra de fonte.

    Pertinência é pergunta **semântica**, e medi-la por proxy foi tentado e falhou: no caso real
    acima, o cosseno de TF-IDF (ADR-0045) deu **0,125 para o trecho fora do assunto e 0,074 para
    o pertinente** — ranking invertido; e a sobreposição de palavras de conteúdo dava zero também
    numa justificativa legítima. Publicar uma guarda que erra assim daria falsa confiança, que é
    pior que não ter guarda. Então a checagem mudou de nível: em vez de **adivinhar**, o contrato
    **pergunta** — o gerador, que é quem vê os dispositivos e o item lado a lado, declara o campo,
    e o validador só lê um booleano. Sem léxico, sem limiar, sem repetir a ADR-0036.

    Args:
        justificativa: a saída do gerador para um item certo/errado.
        dispositivos: os dispositivos ligados a esta questão — a única fonte permitida.

    Returns:
        `Veredito` com `aprovado=True` só quando nenhum motivo de reprovação foi encontrado.
    """
    dispositivos_por_citacao = {
        normalizar_citacao_para_comparacao(d.citacao_canonica): d.texto for d in dispositivos
    }
    motivos: list[str] = []
    if justificativa.cobertura_insuficiente:
        motivos.append(
            "o gerador declarou que os dispositivos ligados não cobrem o assunto do item — "
            "melhor nenhuma explicação do que uma explicação que não é sobre a questão"
        )
    if not justificativa.afirmacoes_certo:
        motivos.append("faltou justificativa_certo (as duas são obrigatórias)")
    if not justificativa.afirmacoes_errado:
        motivos.append("faltou justificativa_errado (as duas são obrigatórias)")
    for afirmacao in justificativa.afirmacoes_certo:
        motivos.extend(_motivos_da_afirmacao(afirmacao, dispositivos_por_citacao, rotulo="certo"))
    for afirmacao in justificativa.afirmacoes_errado:
        motivos.extend(_motivos_da_afirmacao(afirmacao, dispositivos_por_citacao, rotulo="errado"))
    return Veredito(aprovado=not motivos, motivos=motivos)


def verificar_justificativa_multipla_escolha(
    justificativa: JustificativaMultiplaEscolha,
    dispositivos: list[DispositivoParaJustificar],
    letras_esperadas: list[str],
) -> Veredito:
    """Valida mecanicamente uma `JustificativaMultiplaEscolha`.

    Reprova quando: falta a justificativa de alguma das `letras_esperadas` (as cinco são
    obrigatórias — regra 3 da tarefa, "por que a correta é correta e, para cada distrator, por
    que não é"); alguma afirmação cita dispositivo fora dos `dispositivos` recebidos; ou o
    `trecho_que_decide` de alguma afirmação não existe literalmente no dispositivo citado.

    Args:
        justificativa: a saída do gerador para uma questão de múltipla escolha.
        dispositivos: os dispositivos ligados a esta questão — a única fonte permitida.
        letras_esperadas: as letras que a questão realmente tem (normalmente `["A", ..., "E"]`).

    Returns:
        `Veredito` com `aprovado=True` só quando nenhum motivo de reprovação foi encontrado.
    """
    dispositivos_por_citacao = {
        normalizar_citacao_para_comparacao(d.citacao_canonica): d.texto for d in dispositivos
    }
    motivos: list[str] = []
    por_letra = {alternativa.letra: alternativa for alternativa in justificativa.alternativas}

    for letra in letras_esperadas:
        alternativa = por_letra.get(letra)
        if alternativa is None or not alternativa.afirmacoes:
            motivos.append(f"faltou justificativa da alternativa {letra}")
            continue
        for afirmacao in alternativa.afirmacoes:
            motivos.extend(
                _motivos_da_afirmacao(afirmacao, dispositivos_por_citacao, rotulo=f"alt {letra}")
            )

    extras = sorted(set(por_letra) - set(letras_esperadas))
    if extras:
        motivos.append(f"alternativas fora do esperado: {extras}")
    return Veredito(aprovado=not motivos, motivos=motivos)


def montar_texto(afirmacoes: list[Afirmacao]) -> str:
    """Concatena as afirmações aprovadas num único texto, com a citação ao final de cada uma.

    Args:
        afirmacoes: as afirmações já aprovadas pelo validador, na ordem de exibição.

    Returns:
        As frases separadas por espaço, cada uma seguida de `"[<dispositivo>]"`.
    """
    return " ".join(f"{afirmacao.texto} [{afirmacao.dispositivo}]" for afirmacao in afirmacoes)


class AfirmacaoExibicao(BaseModel):
    """Uma frase de `montar_texto` já separada da citação que a encerra, pronta para a tela.

    Attributes:
        texto: a frase, sem o `"[dispositivo]"` que a encerrava.
        dispositivo: a citação exatamente como o gerador escreveu (ex.: `"Lei 8.429/1992 art.
            1"`) — quem exibe é que decide se casa com um `DispositivoLegal` (normalizando com
            `dominio.citacao.normalizar_citacao_para_comparacao`) para mostrar o trecho literal.
            `None` só quando `texto` não seguia o formato de `montar_texto` (defensivo: nunca
            deveria acontecer com texto gravado por ela, mas a tela não quebra se acontecer —
            aparece sem citação, em vez de sumir a frase inteira).
    """

    texto: str
    dispositivo: str | None


_AFIRMACAO_COM_CITACAO = re.compile(r"(.*?)\s*\[([^\]]+)\]")
"""Casa `"<frase> [<dispositivo>]"` — não-guloso, para parar no primeiro `]` de cada afirmação
quando várias estão concatenadas por espaço (formato de `montar_texto`)."""


def separar_afirmacoes(texto: str | None) -> list[AfirmacaoExibicao]:
    """Desfaz `montar_texto`: separa cada frase da citação `"[dispositivo]"` que a encerra.

    Usado pela tela de resultado (`api.questoes`) para renderizar cada afirmação da
    justificativa com a fonte legal ao lado, em vez do texto cru com colchetes. Ausência (`texto`
    `None`/vazio — a maioria das questões hoje, sem justificativa gerada ainda) devolve lista
    vazia, não um item vazio: é o que permite a tela não mostrar nada, silenciosamente, quando
    não há justificativa (regra de exibição do passo 6 — "ausência é silenciosa").

    Args:
        texto: o texto gravado em `Questao.justificativa_certo`/`_errado` ou
            `Alternativa.justificativa` (formato de `montar_texto`); `None` quando a questão
            ainda não tem justificativa.

    Returns:
        Uma `AfirmacaoExibicao` por frase, na ordem em que aparecem; lista vazia se `texto` é
        `None`/vazio. Se o texto não tiver nenhum `"[...]"` reconhecível (não deveria acontecer
        com texto de `montar_texto`, mas texto de outra origem não pode quebrar a tela), devolve
        uma única `AfirmacaoExibicao` com o texto inteiro e `dispositivo=None`.
    """
    if not texto:
        return []
    encontradas = [
        (frase.strip(), dispositivo.strip())
        for frase, dispositivo in _AFIRMACAO_COM_CITACAO.findall(texto)
        if frase.strip()
    ]
    if not encontradas:
        return [AfirmacaoExibicao(texto=texto.strip(), dispositivo=None)]
    return [
        AfirmacaoExibicao(texto=frase, dispositivo=dispositivo)
        for frase, dispositivo in encontradas
    ]
