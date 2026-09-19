"""Plano do dia (fatia 8, F3.x): candidatos de bloco por regras, sem LLM.

O que é: `TopicoParaPlano` (o que a trilha já sabe de um tópico, mais a flag de aula publicada),
`CandidatoBloco`/`BlocoPlanejado` (um bloco possível e um bloco já posicionado, com `ordem` e
`hora_sugerida`), `ResultadoPlano` (a saída de `montar_plano`) e as funções puras: `montar_
candidatos` (revisão de cartões vencidos sempre primeiro; regime restrito para depois dela;
tópico dominado ou sem aula/questão nunca é candidato — a escassez é tratada por omissão, não por
mensagem de erro), `selecionar_blocos` (greedy determinístico pelo tempo disponível),
`montar_plano` (a função pública: aplica as duas de cima, atribui `ordem`/`hora_sugerida` e monta
o `porque_geral`) e `escolher_substituto` (o "discordar" — F3.3/F3.4: a próxima alternativa que
ainda não está no plano e cabe no tempo que sobra). Na semana da prova (RF-19, fatia 10 §7),
`montar_plano` também acrescenta um bloco `"descanso"` sempre por último
(`_garantir_bloco_de_descanso_da_semana_prova`) — o último a ser cortado pelo orçamento, nunca o
primeiro. Nenhuma função lê banco, chama `datetime.now` ou usa `random` —
`dados/repositorio_plano.py` monta a entrada; `api/plano.py`/`motor/plano.py` decidem o que fazer
com a saída. Quando ler: ao mexer em quais blocos entram no plano, no texto do porquê, ou na
troca de um bloco.

**Por que sem LLM** (plano `docs/fatias/8-plano-do-dia.md` §7): a cota do free tier está esgotada
e o `porque`/`porque_geral` já saem determinísticos, com os números reais (quantos cartões,
quantas questões publicáveis, o motivo da trilha) — cumprem o contrato (F3.3 CA: "nenhuma decisão
do agente sem campo `porque`") sem depender de um agente. A arquitetura (§3) já previa "o LLM não
decide o plano"; aqui as regras também escrevem o porquê, não só escolhem os candidatos.

**Determinismo:** nenhuma função usa `random`. A mesma entrada produz sempre a mesma saída —
`montar_plano` é testado exatamente por isso.
"""

from datetime import time
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel

TipoBloco = Literal["aula", "questoes", "revisao", "resumo", "descanso"]
Modo = Literal["normal", "descanso", "semana_prova"]
StatusTrilha = Literal["nao_visto", "fraco", "dominado"]

#: Abaixo desta energia (1–5), nenhum bloco de conteúdo novo entra — só revisão (F3.2 CA:
#: "energia ≤ 2"; `energia < ENERGIA_MINIMA_PARA_ITEM_NOVO` com o valor abaixo é o mesmo corte).
ENERGIA_MINIMA_PARA_ITEM_NOVO: Final = 3

#: Abaixo destas horas de sono, nenhum bloco de conteúdo novo entra — só revisão (F3.2 CA).
SONO_MINIMO_H: Final = 5.0

#: Minutos estimados por cartão vencido, para dimensionar o bloco de revisão.
MINUTOS_POR_CARTAO: Final = 1.5

#: Limites do bloco de revisão: nunca menor que isto (não vale a pena um bloco de 2 min), nunca
#: maior que isto (não vira o dia inteiro só de revisão).
DURACAO_REVISAO_MIN_MIN: Final = 10
DURACAO_REVISAO_MAX_MIN: Final = 40

#: Duração-alvo de um bloco de questões e de um bloco de aula (mesma constante-espírito de
#: `motor/aula.py --tempo-alvo-min 25`).
DURACAO_QUESTOES_MIN: Final = 20
DURACAO_AULA_MIN: Final = 25

#: Duração do bloco de descanso da semana da prova (RF-19: "revisão cirúrgica **+ descanso**").
#: Curto de propósito — não é uma pausa cronometrada de verdade, é o registro de que descansar é
#: parte do plano, não uma folga informal fora dele.
DURACAO_DESCANSO_SEMANA_PROVA_MIN: Final = 15

#: Teto de blocos por dia (o protótipo mostra 5 blocos em 2h) — não deixa o plano virar uma lista
#: infinita quando `tempo_min` é grande.
MAXIMO_BLOCOS: Final = 5

#: Profundidade da trilha considerada — bound de custo: tópicos não-dominados além disto não
#: caberiam em nenhum `tempo_min` realista do piloto.
TOPICOS_CANDIDATOS_MAX: Final = 6

#: Janela da "semana da prova" (RF-19, fatia 10 §7, fecha a P-55): `dias_para_prova` dentro de
#: `[0, DIAS_JANELA_SEMANA_PROVA]` liga o regime de revisão cirúrgica — sem tópico novo, sem
#: aula nova, só cartão vencido e tópico já visto e fraco.
DIAS_JANELA_SEMANA_PROVA: Final = 7

#: As quatro opções fixas de motivo do "discordar" (F3.3 CA) — chave gravada no evento, rótulo
#: para o formulário. Mesmo padrão de `dominio.rotina.OPCOES_HORARIO`.
MOTIVOS_DISCORDAR: Final[tuple[tuple[str, str], ...]] = (
    ("cansada", "Estou cansada agora"),
    ("sem_tempo", "Não tenho tempo para isso agora"),
    ("ja_sei", "Já sei bem esse assunto"),
    ("prefiro_outro", "Prefiro estudar outra coisa"),
)

#: Horário de início sugerido por `perfil_estudo.horario_preferido` (mockup:
#: 2026-09-14-prototipo-clicavel). `"varia"` e qualquer valor desconhecido caem no meio-termo.
_INICIO_POR_HORARIO: Final[dict[str, time]] = {
    "manha": time(6, 30),
    "noite": time(19, 0),
    "varia": time(8, 0),
}


class TopicoParaPlano(BaseModel):
    """O que o planejador precisa saber de um tópico do edital, já na ordem da trilha.

    Attributes:
        topico_id: chave do tópico.
        slug: `Topico.slug`.
        nome: nome de exibição.
        materia: matéria do tópico.
        questoes_publicaveis: peso medido (mesmo campo de `dominio.trilha.TopicoParaTrilha`).
        tem_aula: `True` quando há aula publicada para este tópico (direta ou por equivalência —
            `dados.repositorio_aula.aula_publicada_do_topico`).
        status: `dominio.trilha.ItemTrilha.status` — tópico "dominado" nunca vira candidato.
        motivo_trilha: `dominio.trilha.ItemTrilha.motivo` — a razão real (peso + histórico) que
            o `porque` do bloco cita.
    """

    topico_id: UUID
    slug: str
    nome: str
    materia: str
    questoes_publicaveis: int
    tem_aula: bool
    status: StatusTrilha
    motivo_trilha: str


class CandidatoBloco(BaseModel):
    """Um bloco possível, ainda sem posição no dia (`ordem`/`hora_sugerida`).

    Attributes:
        tipo: `"revisao"`, `"aula"` ou `"questoes"` (fatia 8) e `"descanso"` (fatia 10, RF-19 —
            só na semana da prova, sempre por último); `"resumo"` fica reservado no esquema
            (ver plano §8).
        topico_id: `None` para `"revisao"` e para `"descanso"` (nenhum dos dois é de um tópico).
        duracao_min: estimativa de duração.
        porque: a frase pt-BR pronta para a tela — nunca vazia.
    """

    tipo: TipoBloco
    topico_id: UUID | None
    duracao_min: int
    porque: str


class BlocoPlanejado(BaseModel):
    """Um `CandidatoBloco` já posicionado no dia — o que `Bloco` (ORM) grava.

    Attributes:
        ordem: posição no dia, a partir de 1.
        tipo: ver `CandidatoBloco.tipo`.
        topico_id: ver `CandidatoBloco.topico_id`.
        duracao_min: ver `CandidatoBloco.duracao_min`.
        hora_sugerida: relógio determinístico a partir de `horario_preferido` mais o acumulado
            das durações anteriores.
        porque: ver `CandidatoBloco.porque`.
    """

    ordem: int
    tipo: TipoBloco
    topico_id: UUID | None
    duracao_min: int
    hora_sugerida: time
    porque: str


class ResultadoPlano(BaseModel):
    """O que `montar_plano` devolve — o que `PlanoDia`/`Bloco` (ORM) gravam.

    Attributes:
        modo: `"normal"`, `"descanso"` ou `"semana_prova"` (RF-19, fatia 10 §7, fecha a P-55) —
            `"semana_prova"` sai quando `dias_para_prova` cai na janela de
            `DIAS_JANELA_SEMANA_PROVA` e o dia não é de descanso (descansar continua vencendo:
            regra de saúde, visão §4).
        tempo_min: o orçamento de tempo usado para montar este plano.
        porque_geral: a explicação final — nunca vazia, mesmo com `blocos=[]`.
        blocos: os blocos do dia, na ordem; vazio quando o regime é restrito sem cartão vencido,
            quando a aluna pediu para descansar, ou quando não há candidato nenhum (escassez).
    """

    modo: Modo
    tempo_min: int
    porque_geral: str
    blocos: list[BlocoPlanejado]


def _clamp(valor: int, minimo: int, maximo: int) -> int:
    """`valor` limitado ao intervalo fechado `[minimo, maximo]`."""
    return max(minimo, min(maximo, valor))


def _plural(quantidade: int, singular: str, plural: str) -> str:
    """`singular` para `1`, `plural` para qualquer outro valor (`0` incluso)."""
    return singular if quantidade == 1 else plural


def _em_semana_prova(dias_para_prova: int | None) -> bool:
    """`True` quando `dias_para_prova` cai na janela da semana da prova (RF-19)."""
    return dias_para_prova is not None and 0 <= dias_para_prova <= DIAS_JANELA_SEMANA_PROVA


def _frase_dias_para_prova(dias_para_prova: int) -> str:
    """Monta "Faltam N dias para a prova" (ou "Falta 1 dia") — cabeçalho da semana da prova.

    Args:
        dias_para_prova: sempre `>= 0` neste ponto (`_em_semana_prova` já garantiu a janela).
    """
    verbo = _plural(dias_para_prova, "Falta", "Faltam")
    dia = _plural(dias_para_prova, "dia", "dias")
    return f"{verbo} {dias_para_prova} {dia} para a prova"


def _bloco_descanso_semana_prova(dias_para_prova: int) -> CandidatoBloco:
    """O bloco de descanso que RF-19 pede sempre por último na semana da prova.

    Args:
        dias_para_prova: sempre `>= 0` neste ponto (`_em_semana_prova` já garantiu a janela).
    """
    frase = _frase_dias_para_prova(dias_para_prova)
    return CandidatoBloco(
        tipo="descanso",
        topico_id=None,
        duracao_min=DURACAO_DESCANSO_SEMANA_PROVA_MIN,
        porque=(
            f"{frase} — na semana da prova, descansar é parte do plano: memória consolida "
            "fora do estudo."
        ),
    )


def _garantir_bloco_de_descanso_da_semana_prova(
    selecionados: list[CandidatoBloco], descanso: CandidatoBloco, tempo_min: int
) -> list[CandidatoBloco]:
    """Acrescenta `descanso` ao fim de `selecionados`, abrindo espaço se for preciso.

    RF-19: na semana da prova, o plano sempre termina com o bloco de descanso — ele é o
    **último** a ser cortado, nunca o primeiro. Quando o orçamento (`tempo_min`) ou o teto de
    blocos (`MAXIMO_BLOCOS`) não deixam espaço, remove o candidato de conteúdo mais recente
    (nunca a revisão, que é sempre o cartão vencido do dia) até caber; se não sobrar mais nada
    para remover e ainda assim não couber, o descanso entra do mesmo jeito — a regra de saúde
    (visão §4) vence o orçamento, igual ao pedido explícito de descanso.

    Args:
        selecionados: os blocos já escolhidos por `selecionar_blocos` (revisão + tópicos
            fracos), antes de ganhar posição/horário.
        descanso: o candidato de descanso (`_bloco_descanso_semana_prova`).
        tempo_min: o orçamento de tempo do dia.

    Returns:
        `selecionados` (possivelmente reduzido, cortando do fim para o começo) com `descanso`
        sempre acrescentado por último.
    """
    resultado = list(selecionados)
    while True:
        cabe_tempo = sum(b.duracao_min for b in resultado) + descanso.duracao_min <= tempo_min
        cabe_teto = len(resultado) + 1 <= MAXIMO_BLOCOS
        if cabe_tempo and cabe_teto:
            return [*resultado, descanso]
        indice_removivel = next(
            (i for i in range(len(resultado) - 1, -1, -1) if resultado[i].tipo != "revisao"),
            None,
        )
        if indice_removivel is None:
            # Só sobrou a revisão (ou nada) e ainda não cabe — nada mais para cortar; o
            # descanso entra do mesmo jeito, como o pedido explícito de descanso também vence
            # o orçamento.
            return [*resultado, descanso]
        resultado.pop(indice_removivel)


def montar_candidatos(
    topicos: list[TopicoParaPlano],
    cartoes_vencidos_qtd: int,
    restrito: bool,
    *,
    dias_para_prova: int | None = None,
) -> list[CandidatoBloco]:
    """Monta a lista ordenada de candidatos, antes de cortar pelo tempo disponível.

    Args:
        topicos: os tópicos do edital do concurso principal, já na ordem da trilha (peso medido +
            histórico — `dados.repositorio_plano` monta).
        cartoes_vencidos_qtd: quantos cartões (`repositorio_cartao.cartoes_vencidos`) estão
            vencidos agora.
        restrito: `True` quando o regime do dia (energia baixa, sono baixo, ou pedido explícito
            de descanso) permite só revisão — nenhum candidato de conteúdo novo entra.
        dias_para_prova: dias até `perfil_estudo.data_alvo`, ou `None` sem data marcada (RF-19,
            fatia 10 §7). Dentro de `[0, DIAS_JANELA_SEMANA_PROVA]` liga a revisão cirúrgica: nem
            tópico nunca visto nem aula nova entram, só cartão vencido e tópico já visto e fraco
            (`status == "fraco"`) — `restrito` continua tendo prioridade (já é mais restritivo:
            nenhum tópico entra de jeito nenhum).

    Returns:
        Um candidato de revisão primeiro (se houver cartão vencido). Em regime restrito, só ele.
        Na semana da prova (e não restrito), um candidato `"questoes"` por tópico `"fraco"` com
        questão publicável — nunca `"aula"`, nunca tópico `"nao_visto"`. Fora da semana da prova
        e não restrito, o comportamento de sempre: `"aula"` (se publicada) e `"questoes"` (se
        houver questão) para cada tópico não-dominado, na ordem da trilha. Tópico sem aula e sem
        questão nenhuma nunca gera candidato.
    """
    em_semana_prova = _em_semana_prova(dias_para_prova)
    candidatos: list[CandidatoBloco] = []
    if cartoes_vencidos_qtd > 0:
        duracao = _clamp(
            round(cartoes_vencidos_qtd * MINUTOS_POR_CARTAO),
            DURACAO_REVISAO_MIN_MIN,
            DURACAO_REVISAO_MAX_MIN,
        )
        plural = _plural(cartoes_vencidos_qtd, "cartão venceu", "cartões venceram")
        porque = (
            f"{cartoes_vencidos_qtd} {plural} hoje — é o que está prestes a escapar da memória."
        )
        if em_semana_prova:
            assert dias_para_prova is not None  # `_em_semana_prova` já garantiu isto
            porque = (
                f"{porque} {_frase_dias_para_prova(dias_para_prova)} — revisão cirúrgica, "
                "sem assunto novo."
            )
        candidatos.append(
            CandidatoBloco(tipo="revisao", topico_id=None, duracao_min=duracao, porque=porque)
        )

    if restrito:
        return candidatos

    if em_semana_prova:
        assert dias_para_prova is not None  # `_em_semana_prova` já garantiu isto
        frase = _frase_dias_para_prova(dias_para_prova)
        for topico in topicos[:TOPICOS_CANDIDATOS_MAX]:
            if topico.status != "fraco" or topico.questoes_publicaveis <= 0:
                continue
            candidatos.append(
                CandidatoBloco(
                    tipo="questoes",
                    topico_id=topico.topico_id,
                    duracao_min=DURACAO_QUESTOES_MIN,
                    porque=(
                        f"{frase} — revisão cirúrgica, sem assunto novo. Questões de "
                        f"{topico.nome} ({topico.materia}): {topico.motivo_trilha}."
                    ),
                )
            )
        return candidatos

    for topico in topicos[:TOPICOS_CANDIDATOS_MAX]:
        if topico.status == "dominado":
            continue
        if topico.tem_aula:
            candidatos.append(
                CandidatoBloco(
                    tipo="aula",
                    topico_id=topico.topico_id,
                    duracao_min=DURACAO_AULA_MIN,
                    porque=f"Aula de {topico.nome} ({topico.materia}): {topico.motivo_trilha}.",
                )
            )
        if topico.questoes_publicaveis > 0:
            candidatos.append(
                CandidatoBloco(
                    tipo="questoes",
                    topico_id=topico.topico_id,
                    duracao_min=DURACAO_QUESTOES_MIN,
                    porque=(
                        f"Questões de {topico.nome} ({topico.materia}): {topico.motivo_trilha}."
                    ),
                )
            )
    return candidatos


def selecionar_blocos(candidatos: list[CandidatoBloco], tempo_min: int) -> list[CandidatoBloco]:
    """Escolhe, na ordem de `candidatos`, os que cabem em `tempo_min` (greedy determinístico).

    O primeiro candidato, quando é de revisão, entra sempre inteiro — mesmo estourando
    `tempo_min` (um cartão vencido não espera o orçamento de tempo sobrar). Os demais entram
    enquanto a soma acumulada mais a duração do próximo ainda cabe, até `MAXIMO_BLOCOS`. Nunca
    corta um candidato ao meio.

    Args:
        candidatos: de `montar_candidatos`, já na ordem de prioridade.
        tempo_min: minutos disponíveis no dia.

    Returns:
        O prefixo de `candidatos` que coube, respeitando `MAXIMO_BLOCOS`; vazio sem candidato
        nenhum.
    """
    selecionados: list[CandidatoBloco] = []
    soma = 0
    for indice, candidato in enumerate(candidatos):
        if len(selecionados) >= MAXIMO_BLOCOS:
            break
        obrigatorio = indice == 0 and candidato.tipo == "revisao"
        cabe = soma + candidato.duracao_min <= tempo_min
        if cabe or obrigatorio:
            selecionados.append(candidato)
            soma += candidato.duracao_min
    return selecionados


def _somar_minutos(inicio: time, minutos: int) -> time:
    """`inicio` deslocado em `minutos` (cíclico em 24h — não deveria acontecer na prática)."""
    total = (inicio.hour * 60 + inicio.minute + minutos) % (24 * 60)
    return time(total // 60, total % 60)


def _atribuir_ordem_e_hora(
    selecionados: list[CandidatoBloco], horario_preferido: str
) -> list[BlocoPlanejado]:
    """Atribui `ordem` (1..N) e `hora_sugerida` aos candidatos já selecionados.

    Args:
        selecionados: de `selecionar_blocos`.
        horario_preferido: `perfil_estudo.horario_preferido` (`"manha"`/`"noite"`/`"varia"`).

    Returns:
        Um `BlocoPlanejado` por candidato, na mesma ordem.
    """
    inicio = _INICIO_POR_HORARIO.get(horario_preferido, _INICIO_POR_HORARIO["varia"])
    acumulado = 0
    blocos: list[BlocoPlanejado] = []
    for indice, candidato in enumerate(selecionados, start=1):
        blocos.append(
            BlocoPlanejado(
                ordem=indice,
                tipo=candidato.tipo,
                topico_id=candidato.topico_id,
                duracao_min=candidato.duracao_min,
                hora_sugerida=_somar_minutos(inicio, acumulado),
                porque=candidato.porque,
            )
        )
        acumulado += candidato.duracao_min
    return blocos


def motivo_geral_do_plano(
    restrito: bool,
    pediu_descanso: bool,
    blocos: list[BlocoPlanejado],
    tempo_min: int,
    topicos: list[TopicoParaPlano],
    *,
    dias_para_prova: int | None = None,
) -> str:
    """Monta o `porque_geral` — nunca vazio, mesmo sem bloco nenhum.

    Args:
        restrito: se o regime do dia permitia só revisão (energia/sono baixos).
        pediu_descanso: se a aluna pediu descanso explicitamente no check-in.
        blocos: os blocos já posicionados (`_atribuir_ordem_e_hora`).
        tempo_min: o orçamento de tempo do dia.
        topicos: todos os tópicos considerados (para explicar a escassez quando é o caso).
        dias_para_prova: mesmo parâmetro de `montar_candidatos` (RF-19) — dentro da janela, o
            texto cita os dias que faltam, mesmo quando não há bloco nenhum para revisar.

    Returns:
        Uma frase pt-BR: com blocos, cita quantos e o tempo total (e os dias até a prova, na
        semana da prova); sem blocos, explica se foi pedido de descanso, regime restrito sem
        cartão vencido, semana da prova sem nada para revisar agora, ou falta de conteúdo —
        citando os tópicos sem aula nem questão, nunca escondendo a causa.
    """
    em_semana_prova = _em_semana_prova(dias_para_prova)
    if blocos:
        total = sum(b.duracao_min for b in blocos)
        plural_blocos = _plural(len(blocos), "bloco", "blocos")
        base = (
            f"Hoje: {len(blocos)} {plural_blocos}, {total} min no total, "
            f"dentro dos {tempo_min} min que você tem."
        )
        if em_semana_prova:
            assert dias_para_prova is not None  # `_em_semana_prova` já garantiu isto
            frase = _frase_dias_para_prova(dias_para_prova)
            return f"{frase} — revisão cirúrgica, sem assunto novo. {base}"
        return base
    if pediu_descanso:
        return "Você pediu para descansar hoje — sem bloco nenhum, é a recomendação certa."
    if restrito:
        return (
            "Hoje é dia de descansar: sua energia ou seu sono não pedem item novo, e não há "
            "cartão vencido para revisar."
        )
    if em_semana_prova:
        assert dias_para_prova is not None  # `_em_semana_prova` já garantiu isto
        frase = _frase_dias_para_prova(dias_para_prova)
        return (
            f"{frase} — revisão cirúrgica, sem assunto novo, mas não há cartão vencido nem "
            "tópico fraco para revisar agora."
        )
    sem_conteudo = sorted(
        {
            t.nome
            for t in topicos
            if t.status != "dominado" and t.questoes_publicaveis == 0 and not t.tem_aula
        }
    )
    if sem_conteudo:
        lista = ", ".join(sem_conteudo[:5])
        return f"Sem aula nem questão disponível ainda para os tópicos que faltam: {lista}."
    return "Você já dominou os tópicos com conteúdo disponível — nada novo para hoje."


def montar_plano(
    topicos: list[TopicoParaPlano],
    cartoes_vencidos_qtd: int,
    tempo_min: int,
    energia: int | None,
    sono_h: float | None,
    pediu_descanso: bool,
    horario_preferido: str,
    dias_para_prova: int | None = None,
) -> ResultadoPlano:
    """A função pública: regime → candidatos → seleção → posição → porquê geral.

    Args:
        topicos: os tópicos do edital do concurso principal, na ordem da trilha.
        cartoes_vencidos_qtd: cartões vencidos agora.
        tempo_min: minutos disponíveis (do perfil, na geração noturna; do check-in, na
            reescrita).
        energia: `1`–`5`, ou `None` (geração noturna sem check-in ainda).
        sono_h: horas de sono, ou `None`.
        pediu_descanso: `True` quando a aluna pediu descanso explicitamente (botão "Hoje quero
            descansar" do check-in).
        horario_preferido: `perfil_estudo.horario_preferido`.
        dias_para_prova: `(perfil_estudo.data_alvo - hoje).days`, ou `None` sem `data_alvo`
            (RF-19, fatia 10 §7, fecha a P-55). Quem calcula a subtração é o chamador
            (`dados.repositorio_plano`) — este módulo não lê relógio nem data.

    Returns:
        O `ResultadoPlano` completo. Precedência de `modo`: `"descanso"` (pedido explícito, ou
        regime restrito por energia/sono sem nenhum bloco — regra de saúde, sempre vence) >
        `"semana_prova"` (`dias_para_prova` na janela) > `"normal"` (demais casos, inclui o
        regime restrito que ainda gerou um bloco de revisão). Na semana da prova, `blocos`
        sempre termina em `tipo="descanso"` (RF-19) — exceto quando o dia inteiro já é de
        descanso (regime restrito sem nenhum bloco: a regra de saúde já cobriu o dia inteiro,
        o bloco explícito por cima do nada seria redundante).
    """
    restrito = (
        pediu_descanso
        or (energia is not None and energia < ENERGIA_MINIMA_PARA_ITEM_NOVO)
        or (sono_h is not None and sono_h < SONO_MINIMO_H)
    )
    if pediu_descanso:
        # O pedido explícito ("Hoje quero descansar") vence até o cartão vencido — é uma
        # decisão da aluna, não uma regra de energia/sono; `restrito` (via energia/sono) ainda
        # deixa a revisão entrar, este caminho não deixa nada.
        blocos: list[BlocoPlanejado] = []
    else:
        candidatos = montar_candidatos(
            topicos, cartoes_vencidos_qtd, restrito, dias_para_prova=dias_para_prova
        )
        selecionados = selecionar_blocos(candidatos, tempo_min)
        # RF-19: a semana da prova sempre termina em descanso — exceto quando o regime ficou
        # tão restrito que nem revisão sobrou (o dia já é de descanso inteiro, regra de saúde).
        vira_semana_prova = _em_semana_prova(dias_para_prova) and not (
            restrito and not selecionados
        )
        if vira_semana_prova:
            assert dias_para_prova is not None  # `_em_semana_prova` já garantiu isto
            selecionados = _garantir_bloco_de_descanso_da_semana_prova(
                selecionados, _bloco_descanso_semana_prova(dias_para_prova), tempo_min
            )
        blocos = _atribuir_ordem_e_hora(selecionados, horario_preferido)

    descanso_forcado = pediu_descanso or (restrito and not blocos)
    modo: Modo
    if descanso_forcado:
        modo = "descanso"
    elif _em_semana_prova(dias_para_prova):
        modo = "semana_prova"
    else:
        modo = "normal"
    porque_geral = motivo_geral_do_plano(
        restrito, pediu_descanso, blocos, tempo_min, topicos, dias_para_prova=dias_para_prova
    )
    return ResultadoPlano(modo=modo, tempo_min=tempo_min, porque_geral=porque_geral, blocos=blocos)


def escolher_substituto(
    candidatos: list[CandidatoBloco],
    bloco_atual: BlocoPlanejado,
    blocos_do_plano: list[BlocoPlanejado],
    tempo_restante: int,
) -> CandidatoBloco | None:
    """O "discordar" (F3.3/F3.4): a próxima alternativa que ainda não está no plano.

    Args:
        candidatos: a lista recalculada de `montar_candidatos` (mesma entrada de hoje).
        bloco_atual: o bloco que a aluna quer trocar.
        blocos_do_plano: todos os blocos do plano de hoje (inclui `bloco_atual`) — usado para
            nunca sugerir um `(tipo, topico_id)` que já está em outro bloco do dia.
        tempo_restante: minutos que sobram no orçamento do dia depois de remover `bloco_atual`
            (`tempo_min` do plano menos a soma dos outros blocos).

    Returns:
        O primeiro candidato elegível (não repetido, cabe no tempo restante); `None` quando não
        há alternativa — a rota mantém o bloco atual e avisa, nunca quebra.
    """
    ocupados = {(b.tipo, b.topico_id) for b in blocos_do_plano}
    for candidato in candidatos:
        chave = (candidato.tipo, candidato.topico_id)
        if chave in ocupados:
            continue
        if candidato.duracao_min <= tempo_restante:
            return candidato
    return None
