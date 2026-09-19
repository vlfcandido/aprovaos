"""Fio da memória (V5): escolhe e explica os itens de tópicos já vistos intercalados no bloco.

O que é: `EstatisticaTopicoVisto` (o que se sabe de um tópico já visto por esta aluna, agregado a
partir de `evento_estudo`), `ItemIntercalado` (um candidato ranqueado, já com o `motivo` pronto
para a tela) e as duas funções puras: `escolher_para_intercalar` (o ranking — critério de erro
recente e tempo sem ver, alternados) e `decidir_proximo_intercalado` (a cadência — a cada
`PERIODO_INTERCALACAO` posições do bloco, a próxima é um item intercalado). Nenhuma das duas lê o
banco: recebem o histórico já agregado (`dados/repositorio_fio_memoria.py` monta) e o instante
"agora" de fora, nunca de `datetime.now`. Quando ler: ao mexer em quais tópicos aparecem
intercalados no bloco de questões, na explicação exibida ou na cadência (a cada quantas questões
nativas aparece uma intercalada). Plano: `docs/fatias/V5-fio-da-memoria.md`.
"""

from collections import deque
from datetime import datetime
from itertools import cycle
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel

#: A cada quantas posições do bloco a próxima é um item intercalado (§3 do plano V5): a cada 3
#: respostas nativas do tópico atual, a 4ª é do fio da memória.
PERIODO_INTERCALACAO = 4

#: Quantos tópicos distintos o ranking tenta reunir por rodada (§2 do plano V5) — o "3" da linha
#: V5 do PRD é o tamanho deste conjunto, não um teto vitalício (a cadência recicla os candidatos,
#: §3 do plano).
QUANTIDADE_PADRAO = 3

Criterio = Literal["erro_recente", "tempo_sem_ver"]


class EstatisticaTopicoVisto(BaseModel):
    """O que se sabe de um tópico já visto por esta aluna, agregado de `evento_estudo`.

    Attributes:
        topico_id: chave do tópico (vocabulário global).
        topico_nome: nome de exibição do tópico.
        materia: matéria do tópico — o `motivo` cita a matéria, não o nome do tópico (mais curto
            e mais perto de como a usuária-piloto descreveu a cena na entrevista).
        ultima_visita: `ocorrido_em` da resposta mais recente deste tópico.
        total_respostas: quantas vezes ela respondeu questões deste tópico.
        erros: quantas dessas respostas erraram.
        ultimo_erro_em: `ocorrido_em` do erro mais recente; `None` se ela nunca errou aqui.
    """

    topico_id: UUID
    topico_nome: str
    materia: str
    ultima_visita: datetime
    total_respostas: int
    erros: int
    ultimo_erro_em: datetime | None


class ItemIntercalado(BaseModel):
    """Um tópico já visto escolhido para intercalar, com a explicação pronta para a tela.

    Attributes:
        topico_id: o tópico de origem — nunca o tópico atual que a aluna está estudando.
        topico_nome: nome de exibição do tópico de origem.
        criterio: por qual fila ele foi escolhido (guardado para teste e depuração; a tela usa
            só `motivo`).
        motivo: o texto pronto para exibir, ex.: "de Direito Constitucional, que você viu há 6
            dias e errou 2 de 3".
    """

    topico_id: UUID
    topico_nome: str
    criterio: Criterio
    motivo: str


def _plural_dia(dias: int) -> str:
    """`"dia"` para 1, `"dias"` para qualquer outro valor (0 inclusive — "há 0 dias" é hoje)."""
    return "dia" if dias == 1 else "dias"


def _motivo(estatistica: EstatisticaTopicoVisto, agora: datetime) -> str:
    """Monta o texto do `motivo` a partir da estatística do tópico (§2 do plano V5).

    Nunca fica negativo: um relógio de teste ligeiramente atrás de `ultima_visita` (ex.: a
    própria resposta que acabou de gerar a estatística) vira "há 0 dias", não um número negativo.
    """
    dias = max((agora - estatistica.ultima_visita).days, 0)
    if estatistica.erros > 0:
        desempenho = f"errou {estatistica.erros} de {estatistica.total_respostas}"
    else:
        desempenho = f"acertou {estatistica.total_respostas} de {estatistica.total_respostas}"
    return f"de {estatistica.materia}, que você viu há {dias} {_plural_dia(dias)} e {desempenho}"


def escolher_para_intercalar(
    topico_atual_id: UUID,
    estatisticas: list[EstatisticaTopicoVisto],
    agora: datetime,
    *,
    quantidade: int = QUANTIDADE_PADRAO,
) -> list[ItemIntercalado]:
    """Ranqueia até `quantidade` tópicos já vistos (exceto o atual) para intercalar.

    Duas filas alternadas (§2 do plano V5): a do erro mais recente primeiro, depois a de quem não
    é visto há mais tempo, repetindo a alternância até reunir `quantidade` tópicos distintos ou
    esgotar as duas filas. Nunca sorteia: a ordem é sempre determinística a partir das
    estatísticas recebidas.

    Args:
        topico_atual_id: o tópico que a aluna está estudando agora — nunca entra na lista.
        estatisticas: o histórico agregado por tópico
            (`dados.repositorio_fio_memoria.estatisticas_topicos_vistos`); pode incluir o tópico
            atual, que é filtrado aqui.
        agora: instante de referência para calcular "há quantos dias" — sempre vindo de fora
            (`dados/base.py::agora_utc`), nunca de `datetime.now` interno.
        quantidade: quantos tópicos tentar reunir (padrão 3 — a linha V5 do PRD).

    Returns:
        Até `quantidade` `ItemIntercalado`, em ordem de prioridade; lista vazia quando não há
        nenhum tópico já visto além do atual — sem histórico, não há fio da memória.
    """
    elegiveis = [e for e in estatisticas if e.topico_id != topico_atual_id]
    if not elegiveis:
        return []

    fila_erro: deque[EstatisticaTopicoVisto] = deque(
        sorted(
            (e for e in elegiveis if e.ultimo_erro_em is not None),
            key=lambda e: cast(datetime, e.ultimo_erro_em),
            reverse=True,
        )
    )
    fila_tempo: deque[EstatisticaTopicoVisto] = deque(
        sorted(elegiveis, key=lambda e: e.ultima_visita)
    )
    filas: dict[Criterio, deque[EstatisticaTopicoVisto]] = {
        "erro_recente": fila_erro,
        "tempo_sem_ver": fila_tempo,
    }
    ciclo = cycle(cast(tuple[Criterio, ...], ("erro_recente", "tempo_sem_ver")))

    usados: set[UUID] = set()
    escolhidos: list[ItemIntercalado] = []
    while len(escolhidos) < quantidade:
        if not fila_erro and not fila_tempo:
            break
        criterio = next(ciclo)
        fila = filas[criterio]
        while fila and fila[0].topico_id in usados:
            fila.popleft()
        if not fila:
            continue
        candidato = fila.popleft()
        usados.add(candidato.topico_id)
        escolhidos.append(
            ItemIntercalado(
                topico_id=candidato.topico_id,
                topico_nome=candidato.topico_nome,
                criterio=criterio,
                motivo=_motivo(candidato, agora),
            )
        )
    return escolhidos


def decidir_proximo_intercalado(
    quantidade_no_bloco: int,
    itens: list[ItemIntercalado],
    *,
    periodo: int = PERIODO_INTERCALACAO,
) -> ItemIntercalado | None:
    """Decide se a próxima posição do bloco é um item intercalado (§3 do plano V5).

    Args:
        quantidade_no_bloco: quantas respostas (nativas ou intercaladas) já aconteceram neste
            bloco (`dados.repositorio_fio_memoria.quantidade_no_bloco`) — `0` na primeira
            pergunta do tópico.
        itens: os candidatos já ranqueados (`escolher_para_intercalar`); vazio quando não há
            histórico — nesse caso a função nunca intercala.
        periodo: a cada quantas posições a próxima é intercalada (padrão `PERIODO_INTERCALACAO`).

    Returns:
        O `ItemIntercalado` a mostrar, ciclando pelos candidatos disponíveis conforme a rodada
        avança; `None` quando não é a vez de intercalar ou não há nenhum candidato.
    """
    if not itens:
        return None
    if quantidade_no_bloco % periodo != periodo - 1:
        return None
    indice = (quantidade_no_bloco // periodo) % len(itens)
    return itens[indice]


def ordem_para_tentar(
    quantidade_no_bloco: int,
    itens: list[ItemIntercalado],
    *,
    periodo: int = PERIODO_INTERCALACAO,
) -> list[ItemIntercalado]:
    """A ordem de tentativa quando a posição pede um item intercalado (§3 do plano V5).

    O primeiro da lista é o escolhido por `decidir_proximo_intercalado`; os demais são os outros
    candidatos do ranking, na mesma ordem circular — para a rota tentar buscar uma questão
    disponível em cada um, antes de desistir e cair na próxima questão nativa (o candidato
    escolhido pode não ter mais questão disponível: todas já respondidas ou reportadas).

    Args:
        quantidade_no_bloco: mesma posição de `decidir_proximo_intercalado`.
        itens: os candidatos já ranqueados (`escolher_para_intercalar`).
        periodo: mesmo período de `decidir_proximo_intercalado`.

    Returns:
        A lista de candidatos a tentar, na ordem de preferência; vazia quando não é a vez de
        intercalar ou não há candidato nenhum.
    """
    escolhido = decidir_proximo_intercalado(quantidade_no_bloco, itens, periodo=periodo)
    if escolhido is None:
        return []
    indice = itens.index(escolhido)
    return itens[indice:] + itens[:indice]
