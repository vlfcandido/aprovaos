"""Repositório do diagnóstico adaptativo (fatia 7, F2.1): monta a entrada de `dominio/diagnostico`.

O que é: `topicos_do_diagnostico` (os tópicos do edital do concurso principal, com se há questão
publicável — nunca finge cobertura) e `respostas_diagnostico` (o histórico já ocorrido, filtrado
pelos `evento_estudo` marcados `dados={"diagnostico": True}`, na ordem em que aconteceram). As duas
funções só leem; `api/diagnostico.py` que decide o que fazer com o resultado (nenhuma tabela nova
guarda "o estado do diagnóstico" — ele é recomputado destes eventos a cada `GET`, plano
`docs/fatias/7-diagnostico-e-rotina.md` §5). Quando ler: ao ligar as rotas de `/diagnostico`.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import EventoEstudo, Questao, Topico, TopicoEdital
from aprovaos.dados.repositorio_questao import contagem_por_topico
from aprovaos.dominio.diagnostico import Confianca, ItemDiagnostico, TopicoDisponivel
from aprovaos.dominio.edital import normalizar_materia


def topicos_do_diagnostico(db: Session, edital_id: UUID) -> list[TopicoDisponivel]:
    """Os tópicos do edital, cada um com `tem_questao` resolvido contra a base publicável.

    Args:
        db: sessão do request.
        edital_id: edital do concurso principal (`repositorio_edital.concurso_principal` →
            `edital_atual`).

    Returns:
        Um `TopicoDisponivel` por tópico do edital; a ordem não importa (`ordenar_candidatos`
        reordena por margem/cobertura). `materia` já passa por `normalizar_materia` (dado velho
        do bug de fusão pode ter a mesma matéria em duas caixas — sem normalizar aqui ela vira
        duas matérias no resultado do diagnóstico).
    """
    contagem = contagem_por_topico(db, edital_id)
    consulta = (
        select(Topico.id, Topico.materia, Topico.nome)
        .join(TopicoEdital, TopicoEdital.topico_id == Topico.id)
        .where(TopicoEdital.edital_id == edital_id)
    )
    return [
        TopicoDisponivel(
            topico_id=topico_id,
            materia=normalizar_materia(materia),
            nome=nome,
            tem_questao=contagem.get(topico_id, 0) > 0,
        )
        for topico_id, materia, nome in db.execute(consulta).all()
    ]


def respostas_diagnostico(db: Session, usuario_id: UUID, edital_id: UUID) -> list[ItemDiagnostico]:
    """As respostas já registradas como parte do diagnóstico, na ordem em que ocorreram.

    Filtra em Python sobre `EventoEstudo.dados` (mesma simplificação, correta na escala do piloto,
    de `repositorio_fio_memoria.quantidade_no_bloco`, P-46) — só entram eventos com
    `dados["diagnostico"] is True`; uma resposta comum (fora do diagnóstico) do mesmo tópico não
    conta aqui.

    Args:
        db: sessão do request.
        usuario_id: aluno.
        edital_id: edital do concurso principal — restringe quais tópicos contam (o tópico é
            vocabulário global).

    Returns:
        Um `ItemDiagnostico` por resposta marcada, ordenado por `ocorrido_em`.
    """
    consulta = (
        select(EventoEstudo, Topico.id, Topico.materia)
        .join(Questao, EventoEstudo.questao_id == Questao.id)
        .join(Topico, Questao.topico_id == Topico.id)
        .join(TopicoEdital, TopicoEdital.topico_id == Topico.id)
        .where(
            TopicoEdital.edital_id == edital_id,
            EventoEstudo.usuario_id == usuario_id,
            EventoEstudo.tipo == "resposta",
        )
        .order_by(EventoEstudo.ocorrido_em)
    )
    respostas: list[ItemDiagnostico] = []
    for evento, topico_id, materia in db.execute(consulta).all():
        if not evento.dados or evento.dados.get("diagnostico") is not True:
            continue
        confianca: Confianca = "certeza" if evento.confianca_declarada == "certeza" else "duvida"
        respostas.append(
            ItemDiagnostico(
                topico_id=topico_id,
                materia=normalizar_materia(materia),
                acertou=bool(evento.acertou),
                confianca=confianca,
            )
        )
    return respostas
