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

Quando ler: antes de mudar o prompt do `gerador-de-justificativa`; ao investigar por que uma
justificativa boa (ou ruim) foi aprovada/reprovada.
"""

from pydantic import BaseModel, Field


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
    """

    afirmacoes_certo: list[Afirmacao]
    afirmacoes_errado: list[Afirmacao]


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

    texto_dispositivo = dispositivos_por_citacao.get(afirmacao.dispositivo)
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
    (regra 4 — zero invenção de fonte); ou o `trecho_que_decide` de alguma afirmação não existe
    literalmente no texto do dispositivo citado (regra 2).

    Args:
        justificativa: a saída do gerador para um item certo/errado.
        dispositivos: os dispositivos ligados a esta questão — a única fonte permitida.

    Returns:
        `Veredito` com `aprovado=True` só quando nenhum motivo de reprovação foi encontrado.
    """
    dispositivos_por_citacao = {d.citacao_canonica: d.texto for d in dispositivos}
    motivos: list[str] = []
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
    dispositivos_por_citacao = {d.citacao_canonica: d.texto for d in dispositivos}
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
