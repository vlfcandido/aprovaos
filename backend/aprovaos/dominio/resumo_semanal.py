"""Resumo semanal cumulativo (fatia 10, F4.4c — fio da memória (c)): o que aconteceu na semana.

O que é: `ItemResumo` (um tópico a revisar, com a frase pronta) e `ResumoSemanal` (a saída de
`montar_resumo`) — a função pura que monta o resumo de sábado: quantas respostas, quantos
acertos (com banda de Wilson — ver abaixo), quais tópicos foram vistos pela primeira vez, quais
merecem revisão (erro mais recente primeiro, no máximo 5) e se algum tópico passou a ser
"dominado" durante a semana. Determinístico e sem LLM (Ruling 36, `docs/fatias/10-painel.md`
§1) — nenhuma frase é gerada por modelo, só composta a partir dos números reais. Nenhuma função
lê banco, chama `datetime.now` ou usa `random`; `dados/repositorio_painel.py` (passo 7, fora
deste escopo) monta a entrada. Quando ler: ao mexer no texto ou nos números do resumo semanal.

**Unificação com o resto do painel:** `RespostaHistorica` é a de `dominio.curva` (mesmo formato:
`topico_id`, `acertou`, `ocorrido_em` em UTC) — não uma cópia local. `ResumoSemanal.acertos` é
`dominio.estatistica.Proporcao` (intervalo de Wilson), não uma contagem simples: a regra 11 do
`CLAUDE.md` ("previsão sempre com intervalo") vale para "acertou X de Y" tanto quanto para
qualquer outro número de proficiência do painel (Ruling 35). `acertos` é `None` só quando não há
nenhuma resposta na semana (`total == 0`) — `intervalo_wilson` recusa `total == 0` de propósito
(regra 11: lacuna declarada, nunca um intervalo fabricado para dado inexistente); a tela já cobre
esse caso com "semana sem estudo registrado" via `respostas == 0`, então `acertos=None` não perde
informação nenhuma.
"""

from datetime import date, datetime
from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from aprovaos.dominio.curva import RespostaHistorica
from aprovaos.dominio.estatistica import Proporcao, intervalo_wilson
from aprovaos.dominio.trilha import LIMIAR_DOMINADO, MINIMO_PARA_DOMINADO

#: Fuso fixo da aluna (Ruling 37, `docs/fatias/10-painel.md` §1): `evento_estudo.ocorrido_em` é
#: sempre UTC; a semana do calendário (segunda a domingo) é lida em `America/Sao_Paulo` até a
#: P-44 (fuso por usuário) fechar.
_FUSO_BRASILIA: Final = ZoneInfo("America/Sao_Paulo")

#: Máximo de itens em `ResumoSemanal.para_rever` — cabe em uma tela (§6 do plano).
MAXIMO_PARA_REVER: Final = 5


class ItemResumo(BaseModel):
    """Um tópico a revisar, com a frase pronta para a tela.

    Attributes:
        topico_nome: nome de exibição do tópico.
        frase: pt-BR, com os números reais desta semana — nunca genérica.
    """

    topico_nome: str
    frase: str


class ResumoSemanal(BaseModel):
    """O resumo cumulativo de uma semana (§6 do plano) — sem LLM (Ruling 36).

    Attributes:
        inicio: primeiro dia da semana (segunda, inclusive).
        fim: último dia da semana (domingo, inclusive).
        respostas: quantas respostas aconteceram dentro de `[inicio, fim]`.
        acertos: `dominio.estatistica.Proporcao` (Wilson) de acerto/total desta janela; `None`
            quando `respostas == 0` (`intervalo_wilson` recusa `total == 0` de propósito — ver
            cabeçalho do módulo).
        topicos_novos: nomes dos tópicos cuja primeira resposta de todos os tempos (em todo o
            histórico recebido por `montar_resumo`) caiu dentro desta janela — não um simples
            "apareceu esta semana", que confundiria reaparecimento com novidade.
        para_rever: até `MAXIMO_PARA_REVER` tópicos com pelo menos um erro nesta janela, do erro
            mais recente para o mais antigo (mesmo critério de `dominio.fio_memoria`).
        conquista: `"N tópico(s) dominado(s) nesta semana"` quando algum tópico cruzou o limiar
            de `dominio.trilha` (`LIMIAR_DOMINADO`/`MINIMO_PARA_DOMINADO`) durante esta janela e
            não estava dominado antes dela; `None` quando não há número real para comemorar — a
            semana sem estudo, ou sem conquista nenhuma, é dita como é.
    """

    inicio: date
    fim: date
    respostas: int
    acertos: Proporcao | None
    topicos_novos: list[str]
    para_rever: list[ItemResumo]
    conquista: str | None


def _plural(quantidade: int, singular: str, plural: str) -> str:
    """`singular` para `1`, `plural` para qualquer outro valor (`0` incluso)."""
    return singular if quantidade == 1 else plural


def _data_local(instante: datetime) -> date:
    """A data-calendário de `instante` (UTC) em `America/Sao_Paulo` (Ruling 37)."""
    return instante.astimezone(_FUSO_BRASILIA).date()


def _dentro_da_semana(instante: datetime, inicio: date, fim: date) -> bool:
    """`True` quando a data local (Brasília) de `instante` cai em `[inicio, fim]`, incluso."""
    dia = _data_local(instante)
    return inicio <= dia <= fim


def _dominado(total: int, corretos: int) -> bool:
    """A mesma definição única de "dominado" do produto — importada de `dominio.trilha`."""
    if total == 0:
        return False
    return total >= MINIMO_PARA_DOMINADO and (corretos / total) >= LIMIAR_DOMINADO


def _nome(nomes_por_topico: dict[UUID, str], topico_id: UUID) -> str:
    """`nomes_por_topico[topico_id]`, ou o próprio id como texto se o nome não veio.

    Nunca quebra o resumo por causa de um tópico sem nome resolvido.
    """
    return nomes_por_topico.get(topico_id, str(topico_id))


def montar_resumo(
    respostas: list[RespostaHistorica],
    nomes_por_topico: dict[UUID, str],
    inicio: date,
    fim: date,
) -> ResumoSemanal:
    """Monta o resumo cumulativo da semana `[inicio, fim]` a partir do histórico completo.

    `respostas` não precisa vir pré-filtrada pela janela: a função aceita (e usa) respostas de
    antes de `inicio` para decidir o que é "novo" nesta semana e se algum tópico passou a ser
    "dominado" durante ela — o recorte para as métricas da própria semana (`respostas`,
    `acertos`, `topicos_novos`, `para_rever`) é feito aqui.

    Args:
        respostas: o histórico relevante da aluna (idealmente desde o início dos estudos, para
            "tópico novo" e "conquista" saírem corretos); respostas fora de `[inicio, fim]` são
            usadas só para esse contexto, nunca contam para `respostas`/`acertos` da semana.
        nomes_por_topico: `topico_id` → nome de exibição.
        inicio: primeiro dia da semana (segunda, inclusive).
        fim: último dia da semana (domingo, inclusive).

    Returns:
        O `ResumoSemanal` — `respostas=0`, `acertos=None`, listas vazias e `conquista=None`
        quando não há nenhuma resposta na janela (semana sem estudo registrado).
    """
    da_semana = [r for r in respostas if _dentro_da_semana(r.ocorrido_em, inicio, fim)]
    antes = {r.topico_id for r in respostas if _data_local(r.ocorrido_em) < inicio}

    total = len(da_semana)
    corretos = sum(1 for r in da_semana if r.acertou)
    acertos = intervalo_wilson(corretos, total) if total > 0 else None

    ids_semana = {r.topico_id for r in da_semana}
    topicos_novos = sorted(_nome(nomes_por_topico, tid) for tid in ids_semana if tid not in antes)

    por_topico_semana: dict[UUID, list[RespostaHistorica]] = {}
    for r in da_semana:
        por_topico_semana.setdefault(r.topico_id, []).append(r)
    com_erro = [
        (tid, itens)
        for tid, itens in por_topico_semana.items()
        if any(not r.acertou for r in itens)
    ]
    com_erro.sort(key=lambda par: max(r.ocorrido_em for r in par[1] if not r.acertou), reverse=True)
    para_rever = [
        ItemResumo(
            topico_nome=_nome(nomes_por_topico, tid),
            frase=(
                f"{_nome(nomes_por_topico, tid)}: acertou {sum(1 for r in itens if r.acertou)} "
                f"de {len(itens)} nesta semana — vale revisar."
            ),
        )
        for tid, itens in com_erro[:MAXIMO_PARA_REVER]
    ]

    por_topico_ate_fim: dict[UUID, list[RespostaHistorica]] = {}
    for r in respostas:
        if _data_local(r.ocorrido_em) <= fim:
            por_topico_ate_fim.setdefault(r.topico_id, []).append(r)
    novos_dominados = 0
    for itens in por_topico_ate_fim.values():
        itens_antes = [r for r in itens if _data_local(r.ocorrido_em) < inicio]
        dominado_antes = _dominado(len(itens_antes), sum(1 for r in itens_antes if r.acertou))
        dominado_fim = _dominado(len(itens), sum(1 for r in itens if r.acertou))
        if dominado_fim and not dominado_antes:
            novos_dominados += 1
    conquista = (
        f"{novos_dominados} {_plural(novos_dominados, 'tópico dominado', 'tópicos dominados')} "
        "nesta semana"
        if novos_dominados > 0
        else None
    )

    return ResumoSemanal(
        inicio=inicio,
        fim=fim,
        respostas=total,
        acertos=acertos,
        topicos_novos=topicos_novos,
        para_rever=para_rever,
        conquista=conquista,
    )
