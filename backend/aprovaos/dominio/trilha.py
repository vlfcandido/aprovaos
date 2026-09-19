"""A ordem defensável dos tópicos de estudo — a trilha (fatia 6, linha 6 do PRD §6).

O que é: `TopicoParaTrilha` (o que a trilha precisa saber de um tópico do edital) e
`montar_trilha`, função pura que ordena os tópicos por dois números reais — nunca por peso
declarado (o edital não tem peso por tópico, só peso uniforme por matéria, lacuna P-39) nem por
dificuldade estimada por "achismo": **peso medido** (nº de questões publicáveis na base,
`motor.dossie.topicos_de_maior_peso`) e **o que a aluna já viu/errou**
(`dados.repositorio_fio_memoria.estatisticas_topicos_vistos`). Nenhuma chamada de rede, banco ou
LLM acontece aqui.

Quando ler: ao mudar o critério de ordenação da trilha, ou ao investigar por que um tópico
apareceu antes/depois de outro. Plano: `docs/fatias/6-trilha-e-aulas.md` §7.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from aprovaos.dominio.fio_memoria import EstatisticaTopicoVisto

Status = Literal["nao_visto", "fraco", "dominado"]

#: Um tópico com `total_respostas >= MINIMO_PARA_DOMINADO` e acerto `>= LIMIAR_DOMINADO` é
#: considerado dominado; abaixo disso, mesmo com 100 % de acerto, o dado ainda é pouco para
#: tirá-lo da frente da trilha.
LIMIAR_DOMINADO = 0.7
MINIMO_PARA_DOMINADO = 3


class TopicoParaTrilha(BaseModel):
    """O que `montar_trilha` precisa saber de um tópico do edital.

    Attributes:
        topico_id: chave do tópico.
        slug: `Topico.slug`.
        nome: nome de exibição.
        materia: matéria do tópico.
        questoes_publicaveis: peso medido (`motor.dossie.TopicoComPeso.questoes_publicaveis`).
    """

    topico_id: UUID
    slug: str
    nome: str
    materia: str
    questoes_publicaveis: int


class ItemTrilha(BaseModel):
    """Um tópico já posicionado na trilha, com o porquê escrito.

    Attributes:
        topico_id: chave do tópico.
        slug: `Topico.slug`.
        nome: nome de exibição.
        materia: matéria do tópico.
        questoes_publicaveis: peso medido.
        status: `"nao_visto"`, `"fraco"` (visto com pouco acerto, ou visto de menos para ter uma
            leitura confiável) ou `"dominado"` (visto o bastante, com bom acerto).
        motivo: o porquê desta posição, com os números reais — nunca "parece difícil".
    """

    topico_id: UUID
    slug: str
    nome: str
    materia: str
    questoes_publicaveis: int
    status: Status
    motivo: str


def _status_e_motivo(
    topico: TopicoParaTrilha, estatistica: EstatisticaTopicoVisto | None
) -> tuple[Status, str]:
    """Decide `status`/`motivo` de um tópico a partir do peso medido e do histórico dela."""
    peso = topico.questoes_publicaveis
    if estatistica is None:
        return "nao_visto", f"{peso} questões publicáveis; ainda não estudado"

    acertos = estatistica.total_respostas - estatistica.erros
    total = estatistica.total_respostas
    taxa = acertos / total if total else 0.0
    placar = f"acertou {acertos} de {total}"
    if total >= MINIMO_PARA_DOMINADO and taxa >= LIMIAR_DOMINADO:
        return "dominado", f"{placar} — {peso} questões publicáveis, já dominado"
    return "fraco", f"{placar} — {peso} questões publicáveis, ainda vale revisar"


def montar_trilha(
    topicos: list[TopicoParaTrilha], vistos: dict[UUID, EstatisticaTopicoVisto]
) -> list[ItemTrilha]:
    """Ordena os tópicos: não visto/fraco primeiro (por peso medido), dominado por último.

    Args:
        topicos: os tópicos do edital com o peso medido de cada um.
        vistos: o histórico agregado (`dados.repositorio_fio_memoria
            .estatisticas_topicos_vistos`), por `topico_id`; tópico ausente daqui é "não visto".

    Returns:
        Os `ItemTrilha`, ordenados por `(grupo de prioridade, -peso medido, slug)` — dentro do
        mesmo grupo (não-visto/fraco à frente, dominado ao final), o mais cobrado vem primeiro;
        nunca reordena por dificuldade estimada.
    """
    itens: list[ItemTrilha] = []
    for topico in topicos:
        status, motivo = _status_e_motivo(topico, vistos.get(topico.topico_id))
        itens.append(
            ItemTrilha(
                topico_id=topico.topico_id,
                slug=topico.slug,
                nome=topico.nome,
                materia=topico.materia,
                questoes_publicaveis=topico.questoes_publicaveis,
                status=status,
                motivo=motivo,
            )
        )

    def chave(item: ItemTrilha) -> tuple[int, int, str]:
        grupo = 1 if item.status == "dominado" else 0
        return grupo, -item.questoes_publicaveis, item.slug

    return sorted(itens, key=chave)
