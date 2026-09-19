"""A curva de domínio (RF-16) e o alerta de atraso (RF-10) — fatia 10 §3 do plano.

O que é: `RespostaHistorica` (o que a curva precisa de cada resposta), `PontoCurva`/`Curva` (a
curva real acumulada por semana e a reta necessária até a data da prova) e `Alerta` — mais as duas
funções puras `montar_curva` e `alerta_da_curva`. "Dominado" usa a definição única do produto
(`LIMIAR_DOMINADO`/`MINIMO_PARA_DOMINADO` de `dominio/trilha.py`) — não é redefinida aqui. Nenhuma
das duas funções lê relógio ou banco: `hoje` sempre entra por parâmetro. Quando ler: ao mudar o
critério de "em dia"/"atrasada", a cadência semanal da curva ou o texto do alerta.
Plano: `docs/fatias/10-painel.md` §3.
"""

import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel

from aprovaos.dominio.trilha import LIMIAR_DOMINADO, MINIMO_PARA_DOMINADO

#: Quantas semanas de histórico recente entram no cálculo do ritmo real (§3 do plano).
JANELA_RITMO_SEMANAS = 4


class RespostaHistorica(BaseModel):
    """Uma resposta, só com o que a curva precisa (agregação por tópico e por dia).

    Attributes:
        topico_id: chave do tópico respondido.
        acertou: se a resposta foi certa.
        ocorrido_em: instante da resposta, em UTC (`evento_estudo.ocorrido_em`).
    """

    topico_id: UUID
    acertou: bool
    ocorrido_em: datetime


class PontoCurva(BaseModel):
    """Um ponto da curva (real ou necessária): o estado de domínio num dia.

    Attributes:
        dia: o dia a que este ponto se refere.
        dominados: quantos tópicos estão dominados nesse dia (estado, não troféu — um tópico pode
            deixar de contar aqui se um erro novo derrubar sua taxa de acerto).
        total_topicos: o total de tópicos do edital (igual em todos os pontos de uma mesma curva).
    """

    dia: date
    dominados: int
    total_topicos: int


class Curva(BaseModel):
    """A curva de domínio de uma aluna: o que ela já fez e o que precisaria fazer.

    Attributes:
        real: os pontos observados, um por semana (segunda a domingo), do início do histórico até
            `hoje`; vazio quando não há nenhuma resposta.
        necessaria: a reta de `(hoje, dominados_hoje)` até `(data_alvo, total_topicos)`; vazia
            quando não há `data_alvo` ou quando ela já passou.
        data_alvo: a data da prova, quando informada.
        lacuna: o motivo de não haver `necessaria` ("sem data da prova" ou "data da prova já
            passou"); `None` quando a curva necessária existe.
        atraso_topicos: quantos tópicos ficariam faltando até `data_alvo` se o ritmo dos últimos
            `JANELA_RITMO_SEMANAS` continuar; `0` quando em dia ou sem `data_alvo`.
    """

    real: list[PontoCurva]
    necessaria: list[PontoCurva]
    data_alvo: date | None
    lacuna: str | None
    atraso_topicos: int


class Alerta(BaseModel):
    """O aviso de atraso (RF-10), recomputado a cada carregamento da tela — nunca uma notificação.

    Attributes:
        titulo: frase curta para o topo do aviso.
        porque: os números que justificam o alerta (tópicos faltantes, semanas restantes).
        ajuste: a ação concreta sugerida, sempre com um número ("estude 2 tópicos a mais por
            semana").
    """

    titulo: str
    porque: str
    ajuste: str


def _inicio_da_semana(dia: date) -> date:
    """A segunda-feira da semana que contém `dia` (semana ISO, segunda a domingo)."""
    return dia - timedelta(days=dia.weekday())


def _dominados_ate(respostas: list[RespostaHistorica], ate: date) -> int:
    """Conta quantos tópicos estão dominados considerando só respostas com `ocorrido_em <= ate`.

    Recomputa do zero a cada chamada (nunca incrementa um contador guardado): é o que garante que
    um erro novo derruba o tópico do domínio, em vez da curva só "acumular troféus".
    """
    por_topico: dict[UUID, list[bool]] = defaultdict(list)
    for resposta in respostas:
        if resposta.ocorrido_em.date() <= ate:
            por_topico[resposta.topico_id].append(resposta.acertou)

    dominados = 0
    for acertos_do_topico in por_topico.values():
        total = len(acertos_do_topico)
        acertos = sum(acertos_do_topico)
        if total >= MINIMO_PARA_DOMINADO and acertos / total >= LIMIAR_DOMINADO:
            dominados += 1
    return dominados


def _pontos_semanais(
    respostas: list[RespostaHistorica], total_topicos: int, hoje: date
) -> list[PontoCurva]:
    """Um `PontoCurva` por semana, da primeira semana com resposta até a semana de `hoje`.

    O dia do ponto é o fim daquela semana (domingo), grampeado em `hoje` para a semana corrente —
    nunca um dia no futuro.
    """
    if not respostas:
        return []

    primeiro_dia = min(resposta.ocorrido_em.date() for resposta in respostas)
    semana = _inicio_da_semana(primeiro_dia)
    semana_de_hoje = _inicio_da_semana(hoje)

    pontos: list[PontoCurva] = []
    while semana <= semana_de_hoje:
        fim_da_semana = semana + timedelta(days=6)
        dia_do_ponto = min(fim_da_semana, hoje)
        pontos.append(
            PontoCurva(
                dia=dia_do_ponto,
                dominados=_dominados_ate(respostas, dia_do_ponto),
                total_topicos=total_topicos,
            )
        )
        semana += timedelta(days=7)
    return pontos


def _ritmo_real_semanal(pontos: list[PontoCurva], hoje: date) -> float:
    """O ritmo real recente (tópicos a mais por semana) nas últimas `JANELA_RITMO_SEMANAS`.

    Nunca negativo: perder domínio não vira "ritmo negativo", vira mais atraso — o ritmo de
    referência para o alerta é sempre `>= 0`.
    """
    if len(pontos) < 2:
        return 0.0

    referencia = hoje - timedelta(weeks=JANELA_RITMO_SEMANAS)
    ponto_base = pontos[0]
    for ponto in pontos:
        if ponto.dia <= referencia:
            ponto_base = ponto
        else:
            break

    semanas = max((hoje - ponto_base.dia).days / 7, 1 / 7)
    ganho = pontos[-1].dominados - ponto_base.dominados
    return max(ganho, 0) / semanas


def _atraso_topicos(
    pontos_reais: list[PontoCurva],
    hoje: date,
    data_alvo: date,
    total_topicos: int,
    dominados_hoje: int,
) -> int:
    """Quantos tópicos ficariam faltando em `data_alvo` se o ritmo real recente continuar.

    `0` quando não falta nada hoje ou quando o ritmo real já é suficiente para fechar a lacuna a
    tempo — a curva nunca "adianta" um atraso que o ritmo atual já resolve.
    """
    topicos_faltantes = total_topicos - dominados_hoje
    if topicos_faltantes <= 0:
        return 0

    semanas_restantes = max((data_alvo - hoje).days / 7, 1 / 7)
    ritmo_real = _ritmo_real_semanal(pontos_reais, hoje)
    projetado = ritmo_real * semanas_restantes
    return max(0, round(topicos_faltantes - projetado))


def montar_curva(
    respostas: list[RespostaHistorica],
    total_topicos: int,
    hoje: date,
    data_alvo: date | None,
) -> Curva:
    """Monta a curva de domínio: o observado e, quando há data da prova, o necessário.

    Args:
        respostas: o histórico de respostas usado para decidir quem está dominado
            (`dados/repositorio_painel.py::respostas_historicas`, fora deste módulo).
        total_topicos: quantos tópicos o edital tem no total.
        hoje: a data de referência (nunca `date.today()` interno).
        data_alvo: a data da prova, quando a aluna já a informou em `/rotina`.

    Returns:
        A `Curva`: `real` sempre presente (mesmo vazia, sem resposta nenhuma); `necessaria` só
        existe com `data_alvo` no futuro ou hoje — sem isso, `lacuna` explica por quê e
        `atraso_topicos` é `0` (regra 11 do `CLAUDE.md`: sem dado, lacuna declarada, nunca uma
        linha inventada).
    """
    real = _pontos_semanais(respostas, total_topicos, hoje)
    dominados_hoje = real[-1].dominados if real else 0

    if data_alvo is None:
        return Curva(
            real=real, necessaria=[], data_alvo=None, lacuna="sem data da prova", atraso_topicos=0
        )
    if data_alvo < hoje:
        return Curva(
            real=real,
            necessaria=[],
            data_alvo=data_alvo,
            lacuna="data da prova já passou",
            atraso_topicos=0,
        )

    necessaria = [
        PontoCurva(dia=hoje, dominados=dominados_hoje, total_topicos=total_topicos),
        PontoCurva(dia=data_alvo, dominados=total_topicos, total_topicos=total_topicos),
    ]
    atraso = _atraso_topicos(real, hoje, data_alvo, total_topicos, dominados_hoje)
    return Curva(
        real=real, necessaria=necessaria, data_alvo=data_alvo, lacuna=None, atraso_topicos=atraso
    )


def alerta_da_curva(curva: Curva, horas_por_semana: float) -> Alerta | None:
    """Decide se mostra o alerta de atraso (RF-10) e monta o ajuste concreto.

    RF-10 pede "no máximo 1 alerta por dia": esta fatia entrega um aviso recomputado a cada
    carregamento da tela (não uma notificação push, fora de escopo aqui — §10 do plano), então a
    CA se cumpre por construção: não existe um segundo alerta guardado em lugar nenhum para
    disparar de novo.

    Args:
        curva: a curva já montada por `montar_curva`.
        horas_por_semana: quantas horas por semana a aluna tem disponíveis (`perfil_estudo
            .horas_por_dia_semana` somado, fora deste módulo) — usada só para tentar traduzir o
            ajuste em minutos por dia; sem essa conversão possível, o ajuste fica só em tópicos.

    Returns:
        `None` quando `curva.atraso_topicos == 0` ou não há `data_alvo`; caso contrário, o
        `Alerta` com um ajuste sempre numérico.
    """
    if curva.data_alvo is None or curva.atraso_topicos <= 0 or not curva.necessaria:
        return None

    hoje = curva.necessaria[0].dia
    data_alvo = curva.necessaria[-1].dia
    dominados_hoje = curva.necessaria[0].dominados
    total_topicos = curva.necessaria[-1].total_topicos
    topicos_faltantes = total_topicos - dominados_hoje

    semanas_restantes = max((data_alvo - hoje).days / 7, 1 / 7)
    ajuste_semanal = max(1, math.ceil(curva.atraso_topicos / semanas_restantes))

    plural = "s" if ajuste_semanal != 1 else ""
    ajuste = f"estude {ajuste_semanal} tópico{plural} a mais por semana"

    ritmo_real = _ritmo_real_semanal(curva.real, hoje)
    if ritmo_real > 0 and horas_por_semana > 0:
        horas_por_topico = horas_por_semana / ritmo_real
        minutos_extra_dia = round(ajuste_semanal * horas_por_topico * 60 / 7)
        if minutos_extra_dia > 0:
            ajuste += f" (cerca de +{minutos_extra_dia} min/dia, na sua rotina atual)"

    porque = (
        f"faltam {topicos_faltantes} de {total_topicos} tópicos e restam "
        f"{semanas_restantes:.1f} semanas até {data_alvo:%d/%m/%Y} — no ritmo atual, "
        f"{curva.atraso_topicos} tópico{'s' if curva.atraso_topicos != 1 else ''} "
        "ficariam faltando"
    )

    return Alerta(
        titulo="Você está abaixo da curva necessária",
        porque=porque,
        ajuste=ajuste,
    )
