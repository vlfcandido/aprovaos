"""Repositório do fio da memória (V5): agrega o histórico e conta a posição no bloco.

O que é: `estatisticas_topicos_vistos` (agregado por tópico — última visita, total de respostas,
erros e o erro mais recente — a partir de `evento_estudo`, escopado ao mesmo edital que
`repositorio_questao.topicos_vistos` já usa) e `quantidade_no_bloco` (quantas respostas, nativas
ou intercaladas, já aconteceram no "bloco" deste tópico — a leitura de `evento_estudo.dados
["bloco_topico_id"]`, gravado por `api/questoes.py`). As duas alimentam as funções puras de
`dominio/fio_memoria.py`; nenhuma decide sozinha o que intercalar. Quando ler: ao ligar o
`GET /topico/{slug}/questoes` à intercalação, ou ao investigar por que um tópico não apareceu no
ranking. Plano: `docs/fatias/V5-fio-da-memoria.md`.
"""

from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import EventoEstudo, Questao, Topico, TopicoEdital
from aprovaos.dominio.fio_memoria import EstatisticaTopicoVisto


def estatisticas_topicos_vistos(
    db: Session, usuario_id: UUID, edital_id: UUID
) -> list[EstatisticaTopicoVisto]:
    """Agrega, por tópico deste edital, o histórico de respostas deste usuário.

    Mesma restrição de `repositorio_questao.topicos_vistos`: o tópico é vocabulário global, o
    `edital_id` decide quais tópicos entram na conta. Um tópico sem nenhuma resposta deste
    usuário simplesmente não aparece — "visto" continua exigindo pelo menos uma resposta.

    Args:
        db: sessão do request.
        usuario_id: aluno.
        edital_id: chave do edital que restringe quais tópicos contam.

    Returns:
        Uma `EstatisticaTopicoVisto` por tópico com pelo menos uma resposta; vazio sem nenhuma.
    """
    erro = case((EventoEstudo.acertou.is_(False), 1), else_=0)
    ultimo_erro_em = case((EventoEstudo.acertou.is_(False), EventoEstudo.ocorrido_em), else_=None)
    consulta = (
        select(
            Topico.id,
            Topico.nome,
            Topico.materia,
            func.max(EventoEstudo.ocorrido_em),
            func.count(EventoEstudo.id),
            func.sum(erro),
            func.max(ultimo_erro_em),
        )
        .join(TopicoEdital, TopicoEdital.topico_id == Topico.id)
        .join(Questao, Questao.topico_id == Topico.id)
        .join(EventoEstudo, EventoEstudo.questao_id == Questao.id)
        .where(
            TopicoEdital.edital_id == edital_id,
            EventoEstudo.usuario_id == usuario_id,
            EventoEstudo.tipo == "resposta",
        )
        .group_by(Topico.id, Topico.nome, Topico.materia)
    )
    estatisticas: list[EstatisticaTopicoVisto] = []
    for linha in db.execute(consulta).all():
        topico_id, nome, materia, ultima_visita, total, erros, erro_mais_recente = linha
        estatisticas.append(
            EstatisticaTopicoVisto(
                topico_id=topico_id,
                topico_nome=nome,
                materia=materia,
                ultima_visita=ultima_visita,
                total_respostas=total,
                erros=erros or 0,
                ultimo_erro_em=erro_mais_recente,
            )
        )
    return estatisticas


def quantidade_no_bloco(db: Session, usuario_id: UUID, topico_id: UUID) -> int:
    """Quantas respostas (nativas ou intercaladas) já aconteceram no bloco deste tópico.

    Um evento pertence ao bloco de `topico_id` quando `evento.dados["bloco_topico_id"]` bate com
    ele — inclusive quando a questão respondida é de **outro** tópico (item intercalado): é isso
    que faz o contador só avançar por resposta de verdade, nunca travar mostrando intercalado para
    sempre (`dominio.fio_memoria.decidir_proximo_intercalado`).

    Simplificação registrada (`docs/fatias/V5-fio-da-memoria.md` §4, `P-46`): filtra em Python
    sobre o `dados` já desserializado, em vez de um operador JSON específico de dialeto — correto
    e simples para a escala do piloto (n=1); vira consulta nativa se a escala exigir.

    Args:
        db: sessão do request.
        usuario_id: aluno.
        topico_id: o tópico cujo bloco está sendo contado.

    Returns:
        A quantidade de eventos deste bloco; `0` na primeira pergunta do tópico.
    """
    eventos = db.scalars(
        select(EventoEstudo).where(
            EventoEstudo.usuario_id == usuario_id, EventoEstudo.tipo == "resposta"
        )
    ).all()
    chave = str(topico_id)
    return sum(
        1
        for evento in eventos
        if evento.dados is not None and evento.dados.get("bloco_topico_id") == chave
    )
