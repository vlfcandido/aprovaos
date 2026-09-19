"""Calibração de questões (fatia 11): eventos agregados → dificuldade/discriminação, ação e fila.

O que é: as regras determinísticas da skill `.claude/skills/calibracao-de-questoes/SKILL.md` —
`RespostaBruta`/`ReporteBruto` (entrada crua da janela, tipicamente 14 dias),
`agregar_metricas` (junta em `MetricasQuestao` por questão, incluindo a discriminação item-resto
quando `n ≥ 30`), `avaliar_questao` (R-0..R-9, a primeira que casa decide),
`montar_fila_humana` (prioriza e corta em ≤ 20 min) e `retroalimentacao_do_lote` (padrão que volta
para o prompt do gerador, hoje só R-5). Nenhuma função aqui lê banco nem `datetime.now` —
`dados/repositorio_calibracao.py` monta a entrada a partir de `evento_estudo`/`reporte_erro`;
`motor/calibrar.py` decide o que fazer com a saída (gravar `calibracao`, atualizar `questao`).
Quando ler: antes de mexer em qualquer regra R-n, ou ao investigar por que uma questão foi/não
foi despublicada.

**Discriminação — o que ela é aqui e o piso declarado:** a skill diz "`discriminacao`:
desconhecido se n < 30 senão calculada", sem fixar fórmula. Usamos a correlação ponto-bisserial
item-resto clássica da Teoria Clássica dos Testes (Crocker & Algina, *Introduction to Classical
and Modern Test Theory*, cap. 16): para cada resposta a uma questão, cruza-se o acerto naquele
item (0/1) com o desempenho do respondente nas **demais** questões da mesma janela (exclui a
própria questão, evita autocorrelação); a correlação de Pearson entre as duas séries é a
discriminação estimada. Precisa de pelo menos `N_MINIMO_DISCRIMINACAO` respostas com informação de
desempenho-resto **e** de variância nas duas séries — sem isso (ex.: uma única aluna respondendo
tudo, todo mundo com o mesmo desempenho geral), o resultado é `"desconhecido"` mesmo com n ≥ 30:
o mecanismo diz por quê no lugar de inventar um número (`NaN`/`0.0` por divisão sem sentido).
"""

from __future__ import annotations

from statistics import mean, pstdev
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel, Field

#: Piso da skill: abaixo disso, discriminação é sempre `"desconhecido"` — 3 respostas não é
#: discriminação. É também o piso mínimo para qualquer regra além de R-0/R-3.
N_MINIMO_DISCRIMINACAO: Final = 30

#: Minutos que cada item da fila humana consome, na ausência de estimativa própria — piso
#: escolhido nesta fatia (a skill não fixa um número; usado para não estourar os 20 min/semana).
MINUTOS_POR_ITEM_FILA: Final = 5

#: Teto duro da fila humana por rodada (skill: "cabe nos 20 min semanais do dono").
LIMITE_MINUTOS_FILA: Final = 20

Acao = Literal["manter", "ajustar", "sinalizar", "despublicar"]
Origem = Literal["original", "inedita"]
Confianca = Literal["certeza", "duvida"]

#: Frases que indicam reporte de gabarito trocado/invertido (R-1).
_GATILHOS_GABARITO: Final = (
    "gabarito invertido",
    "invertido",
    "inverteram",
    "gabarito errado",
    "gabarito parece invertido",
    "contrário da",
    "contraria a",
)

#: Frases que indicam mudança de lei (R-2).
_GATILHOS_LEI_MUDOU: Final = (
    "lei mudou",
    "alterou",
    "desatualizada",
    "desatualizado",
    "revogad",
    "prazo mudou",
    "prazo não é mais",
)

#: Frases que indicam conteúdo faltando (R-3).
_GATILHOS_CONTEUDO_FALTANDO: Final = (
    "texto de apoio",
    "faltou o texto",
    "sem enunciado",
    "faltando o texto",
    "não apareceu",
)


def _tem_gatilho(motivos: list[str], gatilhos: tuple[str, ...]) -> bool:
    """Verdadeiro se algum motivo (case-insensitive) contém alguma das frases-gatilho."""
    motivos_normalizados = [motivo.lower() for motivo in motivos]
    return any(gatilho in motivo for motivo in motivos_normalizados for gatilho in gatilhos)


class RespostaBruta(BaseModel):
    """Uma resposta (`evento_estudo` tipo `resposta`) já dentro da janela de calibração.

    Attributes:
        questao_id: a questão respondida.
        usuario_id: quem respondeu — usado para montar o desempenho-resto de discriminação.
        acertou: se a resposta bateu com o gabarito.
        tempo_ms: tempo gasto, em milissegundos; `None` se não registrado.
        confianca_declarada: `"certeza"`/`"duvida"`, como declarado; `None` se não registrado.
    """

    questao_id: UUID
    usuario_id: UUID
    acertou: bool
    tempo_ms: int | None = None
    confianca_declarada: Confianca | None = None


class ReporteBruto(BaseModel):
    """Um reporte de erro (`reporte_erro`) dentro da janela de calibração.

    Attributes:
        questao_id: a questão reportada.
        motivo: o texto livre do reporte.
    """

    questao_id: UUID
    motivo: str


class MetricasQuestao(BaseModel):
    """Os agregados de uma questão na janela — a entrada de `avaliar_questao` (skill, "Entradas").

    Attributes:
        questao_id: a questão calibrada.
        n: quantas respostas na janela.
        acertos: quantas dessas respostas acertaram.
        tempo_mediano_s: tempo mediano de resposta, em segundos; `None` sem dado.
        confianca_alta_erro: quantas respostas marcadas "certeza" erraram.
        reportes: quantos reportes de erro na janela.
        reportes_motivos: os textos livres dos reportes (para classificar por gatilho).
        dificuldade_est: a estimativa atual gravada em `questao.dificuldade_est`; `None` sem
            estimativa anterior.
        origem: `"original"` (veio de prova real) ou `"inedita"` (gerador validado) — decide se
            R-5 (trivial demais) pode disparar.
        discriminacao: a correlação item-resto já calculada por `agregar_metricas`, ou
            `"desconhecido"` quando `n < N_MINIMO_DISCRIMINACAO` ou sem variância suficiente.
    """

    questao_id: UUID
    n: int
    acertos: int
    tempo_mediano_s: float | None
    confianca_alta_erro: int
    reportes: int
    reportes_motivos: list[str] = Field(default_factory=list)
    dificuldade_est: float | None
    origem: Origem
    discriminacao: float | Literal["desconhecido"]

    @property
    def acerto(self) -> float:
        """Proporção de acerto (0 quando `n == 0`, para nunca dividir por zero)."""
        return self.acertos / self.n if self.n else 0.0

    @property
    def erro_confiante(self) -> float:
        """`confianca_alta_erro` sobre o total de erros (0 quando não há erro nenhum)."""
        erros = self.n - self.acertos
        return self.confianca_alta_erro / erros if erros else 0.0

    @property
    def taxa_reporte(self) -> float:
        """`reportes` sobre `n` (0 quando `n == 0`)."""
        return self.reportes / self.n if self.n else 0.0


class AjusteCalibracao(BaseModel):
    """O veredito de `avaliar_questao` — uma linha do relatório e da tabela `calibracao`.

    Attributes:
        questao_id: a questão avaliada.
        acao: `"manter"`/`"ajustar"`/`"sinalizar"`/`"despublicar"`.
        regra: o identificador da regra que decidiu (`"R-0"`..`"R-9"`).
        evidencia: os números que dispararam a regra, em texto (skill: "toda ação cita a regra e
            os números").
        efeito_colateral: o que mais precisa acontecer (reingestão, propagação, etc.); vazio para
            `"manter"`/`"ajustar"`/`"sinalizar"`, sempre preenchido para `"despublicar"`.
        dificuldade_real: `1 - acerto` — o que vai para `calibracao.dificuldade_real` e, quando a
            ação é `"ajustar"`/`"despublicar"`/R-6/R-7, também para `questao.dificuldade_est`.
        discriminacao: repassada de `MetricasQuestao.discriminacao`, forçada a `"desconhecido"`
            quando `n < N_MINIMO_DISCRIMINACAO` (defesa contra entrada inconsistente).
        n: repassado de `MetricasQuestao.n` — a fila e o relatório nunca escondem o tamanho da
            amostra que decidiu.
    """

    questao_id: UUID
    acao: Acao
    regra: str
    evidencia: str
    efeito_colateral: list[str] = Field(default_factory=list)
    dificuldade_real: float
    discriminacao: float | Literal["desconhecido"]
    n: int


class ItemFilaHumana(BaseModel):
    """Um item da fila do dono — só o que exige julgamento (skill: R-8).

    Attributes:
        questao_id: a questão sinalizada.
        motivo: os motivos de reporte mais frequentes, resumidos.
        o_que_olhar: uma frase dizendo o que checar (skill: obrigatório, "não pode abrir sem
            saber o que procurar").
        minutos_estimados: quanto tempo este item consome da rodada de 20 min.
        regra: sempre `"R-8"` nesta fatia (única regra que alimenta a fila humana).
    """

    questao_id: UUID
    motivo: str
    o_que_olhar: str
    minutos_estimados: int
    regra: str


class RetroalimentacaoGerador(BaseModel):
    """Um padrão que volta para o prompt/DNA do gerador (skill: "retroalimentacao_gerador").

    Attributes:
        questao_id: a questão que originou o padrão (R-5: inédita trivial).
        padrao: a frase que descreve o padrão, para o próximo prompt evitar.
    """

    questao_id: UUID
    padrao: str


def calcular_discriminacao(
    respostas: list[RespostaBruta], desempenho_resto: dict[UUID, tuple[float, int]]
) -> float | Literal["desconhecido"]:
    """Correlação item-resto entre o acerto nesta questão e o desempenho do respondente no resto.

    Todas as `respostas` devem ser da mesma questão (quem cruza questões diferentes é
    `agregar_metricas`). `desempenho_resto[usuario_id]` é `(proporção de acerto nas demais
    respostas da janela, quantidade dessas outras respostas)` — quem não tem nenhuma outra
    resposta na janela (`n_resto == 0`) não entra na correlação (não há "resto" para comparar).

    Args:
        respostas: as respostas a uma única questão, dentro da janela.
        desempenho_resto: o desempenho de cada respondente nas outras questões da mesma janela.

    Returns:
        A correlação de Pearson (`[-1, 1]`, arredondada a 4 casas), ou `"desconhecido"` quando a
        amostra útil (depois de excluir quem não tem "resto") é menor que
        `N_MINIMO_DISCRIMINACAO`, ou quando o acerto no item ou o desempenho-resto não varia
        (correlação matematicamente indefinida — nunca um `NaN`/`0.0` fabricado).
    """
    pares: list[tuple[float, float]] = []
    for resposta in respostas:
        info = desempenho_resto.get(resposta.usuario_id)
        if info is None:
            continue
        proporcao_resto, n_resto = info
        if n_resto <= 0:
            continue
        pares.append((1.0 if resposta.acertou else 0.0, proporcao_resto))

    if len(pares) < N_MINIMO_DISCRIMINACAO:
        return "desconhecido"

    xs = [par[0] for par in pares]
    ys = [par[1] for par in pares]
    desvio_x = pstdev(xs)
    desvio_y = pstdev(ys)
    if desvio_x == 0 or desvio_y == 0:
        return "desconhecido"

    media_x = mean(xs)
    media_y = mean(ys)
    covariancia = mean((x - media_x) * (y - media_y) for x, y in pares)
    correlacao = covariancia / (desvio_x * desvio_y)
    return round(max(-1.0, min(1.0, correlacao)), 4)


def agregar_metricas(
    respostas: list[RespostaBruta],
    reportes: list[ReporteBruto],
    origem_por_questao: dict[UUID, Origem],
    dificuldade_por_questao: dict[UUID, float],
) -> list[MetricasQuestao]:
    """Agrupa respostas e reportes crus por questão e calcula a discriminação item-resto.

    O desempenho-resto de cada respondente é calculado uma única vez a partir de **todas** as
    `respostas` da janela (de qualquer questão) — para a questão N, o resto de um respondente
    exclui só as respostas dele à própria questão N, mas inclui as respostas dele a qualquer
    outra questão da mesma lista.

    Args:
        respostas: todas as respostas (`evento_estudo` tipo `resposta`) da janela, de qualquer
            questão.
        reportes: todos os reportes (`reporte_erro`) da janela, de qualquer questão.
        origem_por_questao: `{questao_id: "original"|"inedita"}`; questão sem entrada aqui não é
            incluída no resultado (não há como calibrar sem saber a origem).
        dificuldade_por_questao: `{questao_id: dificuldade_est atual}`; questão sem entrada fica
            com `dificuldade_est=None`.

    Returns:
        Uma `MetricasQuestao` por `questao_id` presente em `origem_por_questao` com pelo menos
        uma resposta na janela.
    """
    respostas_por_questao: dict[UUID, list[RespostaBruta]] = {}
    for resposta in respostas:
        respostas_por_questao.setdefault(resposta.questao_id, []).append(resposta)

    motivos_por_questao: dict[UUID, list[str]] = {}
    contagem_reportes: dict[UUID, int] = {}
    for reporte in reportes:
        motivos_por_questao.setdefault(reporte.questao_id, []).append(reporte.motivo)
        contagem_reportes[reporte.questao_id] = contagem_reportes.get(reporte.questao_id, 0) + 1

    # Desempenho geral de cada respondente na janela inteira: (acertos_totais, total_respostas).
    desempenho_total: dict[UUID, list[int]] = {}
    for resposta in respostas:
        contador = desempenho_total.setdefault(resposta.usuario_id, [0, 0])
        contador[0] += 1 if resposta.acertou else 0
        contador[1] += 1

    resultado: list[MetricasQuestao] = []
    for questao_id, origem in origem_por_questao.items():
        respostas_da_questao = respostas_por_questao.get(questao_id, [])
        motivos_da_questao = motivos_por_questao.get(questao_id, [])
        if not respostas_da_questao and not motivos_da_questao:
            # Sem resposta e sem reporte: não há o que calibrar (nem R-3 tem gatilho para casar).
            continue

        n = len(respostas_da_questao)
        acertos = sum(1 for resposta in respostas_da_questao if resposta.acertou)
        tempos = [r.tempo_ms for r in respostas_da_questao if r.tempo_ms is not None]
        tempo_mediano_s = (sorted(tempos)[len(tempos) // 2] / 1000) if tempos else None
        confianca_alta_erro = sum(
            1
            for resposta in respostas_da_questao
            if not resposta.acertou and resposta.confianca_declarada == "certeza"
        )

        desempenho_resto: dict[UUID, tuple[float, int]] = {}
        for resposta in respostas_da_questao:
            acertos_totais, total = desempenho_total[resposta.usuario_id]
            acertos_resto = acertos_totais - (1 if resposta.acertou else 0)
            total_resto = total - 1
            if total_resto <= 0:
                desempenho_resto[resposta.usuario_id] = (0.0, 0)
            else:
                desempenho_resto[resposta.usuario_id] = (acertos_resto / total_resto, total_resto)

        discriminacao = calcular_discriminacao(respostas_da_questao, desempenho_resto)

        resultado.append(
            MetricasQuestao(
                questao_id=questao_id,
                n=n,
                acertos=acertos,
                tempo_mediano_s=tempo_mediano_s,
                confianca_alta_erro=confianca_alta_erro,
                reportes=contagem_reportes.get(questao_id, 0),
                reportes_motivos=motivos_por_questao.get(questao_id, []),
                dificuldade_est=dificuldade_por_questao.get(questao_id),
                origem=origem,
                discriminacao=discriminacao,
            )
        )
    return resultado


def avaliar_questao(metricas: MetricasQuestao) -> AjusteCalibracao:
    """Decide a ação de uma questão pela primeira regra R-0..R-9 que casar (skill, "Regras").

    Ordem de avaliação (a exceção documentada pela própria skill): R-3 (conteúdo faltando) é
    checada **antes** do corte de amostra — "vale com qualquer n". Todas as demais regras exigem
    `n ≥ N_MINIMO_DISCRIMINACAO`; abaixo disso, sem R-3, a questão é mantida por R-0.

    Args:
        metricas: os agregados da questão na janela (`agregar_metricas`).

    Returns:
        O `AjusteCalibracao` com a regra, a evidência numérica e o efeito colateral.
    """
    dificuldade_real = 1 - metricas.acerto
    discriminacao_declarada: float | Literal["desconhecido"] = (
        metricas.discriminacao if metricas.n >= N_MINIMO_DISCRIMINACAO else "desconhecido"
    )

    def _ajuste(
        acao: Acao, regra: str, evidencia: str, efeito_colateral: list[str] | None = None
    ) -> AjusteCalibracao:
        return AjusteCalibracao(
            questao_id=metricas.questao_id,
            acao=acao,
            regra=regra,
            evidencia=evidencia,
            efeito_colateral=efeito_colateral or [],
            dificuldade_real=round(dificuldade_real, 4),
            discriminacao=discriminacao_declarada,
            n=metricas.n,
        )

    evidencia_base = (
        f"acerto={metricas.acerto:.2f}, erro_confiante={metricas.erro_confiante:.2f}, "
        f"taxa_reporte={metricas.taxa_reporte:.2f}, n={metricas.n}"
    )

    # R-3 (exceção explícita da skill: "vale com qualquer n") — avaliada antes do corte de amostra.
    if _tem_gatilho(metricas.reportes_motivos, _GATILHOS_CONTEUDO_FALTANDO):
        return _ajuste(
            "despublicar",
            "R-3",
            f"{evidencia_base}, motivos={metricas.reportes_motivos}",
            ["reingestão do documento (verificação 2 da ingestao-de-provas)"],
        )

    if metricas.n < N_MINIMO_DISCRIMINACAO:
        return _ajuste("manter", "R-0", f"{evidencia_base} — amostra abaixo do piso de calibração")

    if (
        metricas.acerto < 0.40
        and metricas.erro_confiante >= 0.20
        and metricas.taxa_reporte >= 0.02
        and _tem_gatilho(metricas.reportes_motivos, _GATILHOS_GABARITO)
    ):
        return _ajuste(
            "despublicar",
            "R-1",
            f"{evidencia_base}, motivos={metricas.reportes_motivos}",
            [
                "reabrir na ingestao-de-provas para conferir gabarito definitivo x preliminar",
                "fila humana só se a reingestão não resolver",
            ],
        )

    if _tem_gatilho(metricas.reportes_motivos, _GATILHOS_LEI_MUDOU):
        return _ajuste(
            "despublicar",
            "R-2",
            f"{evidencia_base}, motivos={metricas.reportes_motivos}",
            [
                "checar dispositivo_legal.vigente das citações",
                "propagar para toda aula/questão que cita o dispositivo (RF-30)",
            ],
        )

    if metricas.acerto < 0.40 and metricas.erro_confiante < 0.20 and metricas.taxa_reporte < 0.02:
        return _ajuste("ajustar", "R-4", f"{evidencia_base} — difícil, não errada")

    if metricas.acerto >= 0.95 and metricas.n >= 100 and metricas.origem == "inedita":
        return _ajuste(
            "despublicar",
            "R-5",
            f"{evidencia_base} — item trivial (inédita, sem variação)",
            ["gerador não recebe crédito de cobertura por este item"],
        )

    if metricas.acerto >= 0.95 and metricas.origem == "original":
        return _ajuste("ajustar", "R-6", evidencia_base)

    if (
        metricas.dificuldade_est is not None
        and abs(metricas.dificuldade_est - dificuldade_real) > 0.15
    ):
        return _ajuste(
            "ajustar",
            "R-7",
            f"{evidencia_base}, dificuldade_est_atual={metricas.dificuldade_est:.2f}, "
            f"dificuldade_real={dificuldade_real:.2f}",
        )

    if metricas.taxa_reporte >= 0.02:
        return _ajuste("sinalizar", "R-8", f"{evidencia_base}, motivos={metricas.reportes_motivos}")

    return _ajuste("manter", "R-9", evidencia_base)


def montar_fila_humana(
    ajustes: list[AjusteCalibracao], metricas_por_id: dict[UUID, MetricasQuestao]
) -> tuple[list[ItemFilaHumana], list[ItemFilaHumana]]:
    """Monta a fila humana (só `sinalizar`, R-8) e separa o que não cabe em 20 minutos.

    Prioriza por `taxa_reporte` decrescente (o que mais alunos reportaram primeiro); cada item
    custa `MINUTOS_POR_ITEM_FILA`. O que não couber no teto vira a segunda lista
    (`fila_humana_adiada` da skill) — nunca é descartado silenciosamente.

    Args:
        ajustes: a saída de `avaliar_questao` para o lote inteiro.
        metricas_por_id: `{questao_id: MetricasQuestao}` do mesmo lote, para ordenar por
            `taxa_reporte` e resumir os motivos em `o_que_olhar`.

    Returns:
        `(fila, adiada)` — ambas ordenadas por prioridade; `sum(minutos) da fila <=
        LIMITE_MINUTOS_FILA`.
    """
    candidatos = [ajuste for ajuste in ajustes if ajuste.regra == "R-8"]
    candidatos.sort(
        key=lambda ajuste: metricas_por_id[ajuste.questao_id].taxa_reporte, reverse=True
    )

    fila: list[ItemFilaHumana] = []
    adiada: list[ItemFilaHumana] = []
    minutos_usados = 0
    for ajuste in candidatos:
        metricas = metricas_por_id[ajuste.questao_id]
        motivos_mais_frequentes = ", ".join(metricas.reportes_motivos[:3]) or "sem motivo detalhado"
        item = ItemFilaHumana(
            questao_id=ajuste.questao_id,
            motivo=motivos_mais_frequentes,
            o_que_olhar=f"conferir os reportes: {motivos_mais_frequentes}",
            minutos_estimados=MINUTOS_POR_ITEM_FILA,
            regra=ajuste.regra,
        )
        if minutos_usados + item.minutos_estimados <= LIMITE_MINUTOS_FILA:
            fila.append(item)
            minutos_usados += item.minutos_estimados
        else:
            adiada.append(item)
    return fila, adiada


def retroalimentacao_do_lote(ajustes: list[AjusteCalibracao]) -> list[RetroalimentacaoGerador]:
    """Extrai os padrões que voltam para o prompt do gerador — hoje só as questões `R-5`.

    Args:
        ajustes: a saída de `avaliar_questao` para o lote inteiro.

    Returns:
        Uma `RetroalimentacaoGerador` por `AjusteCalibracao` com `regra == "R-5"`.
    """
    return [
        RetroalimentacaoGerador(
            questao_id=ajuste.questao_id,
            padrao="item trivial: transcrição literal ou sem variação suficiente (R-5)",
        )
        for ajuste in ajustes
        if ajuste.regra == "R-5"
    ]
