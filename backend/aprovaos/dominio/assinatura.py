"""Regras puras de tier, limites e assinatura (fatia 12 — billing real, ADR-0015, Rulings 46-48).

O que é: `Tier`/`StatusAssinatura`, `LimitesDoTier`/`LIMITES` (o que cada plano permite),
`UsoDoDia` (o que um usuário já consumiu hoje) e as três funções puras que decidem "pode
responder mais uma questão", "pode processar mais um edital com DNA" e "qual tier vale agora
dada uma assinatura". Nada aqui toca banco, HTTP ou relógio — quem chama já traz `uso`/`hoje`
prontos (mesmo padrão de `dominio/curva.py`/`dominio/previsao.py`). Quando ler: antes de mexer no
limite do Free, no aviso da tela de questões, ou na tolerância de assinatura em atraso/cancelada.
"""

from calendar import monthrange
from datetime import date, timedelta
from typing import Final, Literal

from pydantic import BaseModel, Field

Tier = Literal["free", "pro"]
StatusAssinatura = Literal["ativa", "em_atraso", "cancelada", "expirada"]

#: `"mensal"`/`"anual"` (ADR-0015: R$ 59/mês ou R$ 490/ano) — o valor gravado em
#: `assinatura.periodicidade` (`docs/04-modelo-de-dados.md` §2).
Periodicidade = Literal["mensal", "anual"]

#: Quantos meses cada `Periodicidade` cobre — `AutoRecurring.frequency_type` do Mercado Pago só
#: aceita `"months"`/`"days"` (sem `"years"`), então "anual" é 12 meses, não 365 dias.
_MESES_POR_PERIODICIDADE: Final[dict[Periodicidade, int]] = {"mensal": 1, "anual": 12}

#: Regra 5.3 da fábrica (churn involuntário não é churn — citada na visão §9, ADR-0015): quantos
#: dias uma assinatura `em_atraso` (a retentativa do gateway após uma cobrança recusada) ainda
#: vale como Pro, contados a partir do fim do período pago, antes de cair para Free.
DIAS_TOLERANCIA_EM_ATRASO: Final[int] = 10

MENSAGEM_CONVITE_QUESTOES: Final[str] = "Assine o Pro para continuar respondendo hoje."
MENSAGEM_CONVITE_EDITAL: Final[str] = "Assine o Pro para subir outro edital."


class LimitesDoTier(BaseModel):
    """O que um tier permite; `None` em qualquer campo é "sem limite" (hoje, só o Pro).

    Attributes:
        questoes_por_dia: quantas questões (nativas ou inéditas) um usuário pode **responder**
            por dia; `pode_responder` confere isto só ao montar a próxima (Ruling 47) — nunca no
            meio de uma resposta, e nunca para revisão de cartão vencido nem aula publicada
            (essas rotas nem chamam esta função: por construção, não existe caminho para
            limitá-las).
        editais_com_dna: quantos concursos com `dna_concurso` um tenant pode manter (ADR-0015:
            Free = "DNA de 1 concurso" — um teto de recurso do tenant, não uma cota diária).
        ineditas_por_dia: reservado pelo plano da fatia 12 (`docs/fatias/12-billing.md` §2) para
            um teto diário de questões inéditas (geradas por LLM, mais caras) servidas por
            usuário. **Nenhuma ADR/PRD decidiu um número** para este campo — fica `None` nas duas
            tiers até essa decisão existir; o campo continua na forma porque
            `UsoDoDia.ineditas_servidas` já é rastreável hoje (`Questao.inedita`), então a
            decisão pode chegar sem migração nova. Pendência registrada em
            `docs/PENDENCIAS.md`.
    """

    questoes_por_dia: int | None
    editais_com_dna: int | None
    ineditas_por_dia: int | None


LIMITES: Final[dict[Tier, LimitesDoTier]] = {
    "free": LimitesDoTier(questoes_por_dia=20, editais_com_dna=1, ineditas_por_dia=None),
    "pro": LimitesDoTier(questoes_por_dia=None, editais_com_dna=None, ineditas_por_dia=None),
}


class UsoDoDia(BaseModel):
    """O que um usuário já consumiu hoje (`dados/repositorio_uso.py` monta isto).

    Recomputado por consulta em `evento_estudo`, sem tabela própria — mesmo princípio do
    diagnóstico da fatia 7.

    Attributes:
        questoes_respondidas: quantos `evento_estudo(tipo="resposta")` de hoje.
        ineditas_servidas: quantos desses eventos foram de uma `Questao.inedita=True` (reservado
            para quando `LimitesDoTier.ineditas_por_dia` deixar de ser `None`).
    """

    questoes_respondidas: int = Field(ge=0)
    ineditas_servidas: int = Field(ge=0)


class Veredito(BaseModel):
    """O resultado de checar um limite — pronto para a tela, nunca um erro (Ruling 47).

    Attributes:
        permitido: `True` libera a ação.
        motivo: por que não, em pt-BR, pronto para exibir; `None` quando `permitido`.
        quanto_falta: quantas unidades faltam para poder de novo (hoje `0`, sempre "amanhã", já
            que os limites desta fatia são diários); `None` quando `permitido` ou sem teto.
        convite: frase de upgrade, nunca ameaça; `None` quando `permitido`.
    """

    permitido: bool
    motivo: str | None = None
    quanto_falta: int | None = None
    convite: str | None = None


def pode_responder(tier: Tier, uso: UsoDoDia) -> Veredito:
    """Decide se o usuário pode receber mais uma questão hoje (Ruling 47).

    Args:
        tier: o tier efetivo do usuário (`tier_efetivo`).
        uso: quantas questões ele já respondeu hoje.

    Returns:
        `Veredito(permitido=True)` sob o limite (ou sem limite, Pro); acima dele,
        `permitido=False` com `motivo`/`quanto_falta`/`convite` prontos para a tela onde a
        próxima questão apareceria — sem erro, sem modal, sem perder resposta em curso.
    """
    limite = LIMITES[tier].questoes_por_dia
    if limite is None or uso.questoes_respondidas < limite:
        return Veredito(permitido=True)
    return Veredito(
        permitido=False,
        motivo=f"Você já respondeu as {limite} questões de hoje no plano Free.",
        quanto_falta=0,
        convite=MENSAGEM_CONVITE_QUESTOES,
    )


def pode_criar_edital(tier: Tier, editais_com_dna_existentes: int) -> Veredito:
    """Decide se o tenant pode processar o DNA de mais um edital (ADR-0015: Free = 1 concurso).

    Args:
        tier: o tier efetivo do tenant dono do edital.
        editais_com_dna_existentes: quantos concursos deste tenant já têm `dna_concurso`
            (contagem total do tenant, não diária — é um teto de recurso, não uma cota do dia).

    Returns:
        `Veredito` no mesmo formato de `pode_responder`.
    """
    limite = LIMITES[tier].editais_com_dna
    if limite is None or editais_com_dna_existentes < limite:
        return Veredito(permitido=True)
    return Veredito(
        permitido=False,
        motivo=f"O plano Free processa o DNA de {limite} concurso.",
        quanto_falta=0,
        convite=MENSAGEM_CONVITE_EDITAL,
    )


def tier_efetivo(status: StatusAssinatura, fim_do_periodo: date, hoje: date) -> Tier:
    """O tier que vale agora, dado o status da assinatura e o fim do período já pago.

    Regras (plano §2, Ruling 46): `ativa` é sempre Pro; uma assinatura `cancelada` continua Pro
    até `fim_do_periodo` **inclusive** (cancelamento em um clique não devolve o que já foi pago);
    `em_atraso` continua Pro por `DIAS_TOLERANCIA_EM_ATRASO` dias a partir de `fim_do_periodo` —
    a janela de retentativa do gateway (churn involuntário não é churn, regra 5.3 da fábrica);
    `expirada` é sempre Free.

    Args:
        status: o `assinatura.status` gravado.
        fim_do_periodo: `assinatura.fim` — fim do período já pago.
        hoje: a data de referência (nunca `date.today()` direto — quem chama decide "hoje", para
            a função continuar pura e testável).

    Returns:
        `"pro"` ou `"free"`.
    """
    if status == "ativa":
        return "pro"
    if status == "cancelada":
        return "pro" if hoje <= fim_do_periodo else "free"
    if status == "em_atraso":
        limite = fim_do_periodo + timedelta(days=DIAS_TOLERANCIA_EM_ATRASO)
        return "pro" if hoje <= limite else "free"
    return "free"  # status == "expirada"


def calcular_fim_do_periodo(periodicidade: Periodicidade, inicio: date) -> date:
    """O fim do período pago: `inicio` + 1 mês (mensal) ou 12 meses (anual), calendário real.

    Soma meses de verdade (não 30/365 dias) — o mesmo critério do `AutoRecurring.frequency_type`
    do Mercado Pago (`pagamento/mercado_pago.py`). Quando o dia de `inicio` não existe no mês de
    destino (ex.: 31/jan + 1 mês), cai no último dia daquele mês (28 ou 29/fev).

    Args:
        periodicidade: `"mensal"` ou `"anual"`.
        inicio: `assinatura.inicio` (a data, sem hora).

    Returns:
        A data de `assinatura.fim`.
    """
    meses = _MESES_POR_PERIODICIDADE[periodicidade]
    mes_total = inicio.month - 1 + meses
    ano = inicio.year + mes_total // 12
    mes = mes_total % 12 + 1
    ultimo_dia_do_mes = monthrange(ano, mes)[1]
    dia = min(inicio.day, ultimo_dia_do_mes)
    return date(ano, mes, dia)
