"""Uso diário de um usuário, recomputado de `evento_estudo` (fatia 12, Ruling 47).

O que é: `uso_do_dia` — quantas questões um usuário respondeu num dia (UTC) e quantas delas eram
inéditas. Sem tabela própria: mesmo princípio do diagnóstico da fatia 7 (recomputar por consulta
em vez de materializar um contador) — `dominio.assinatura.pode_responder` só confere isto ao
montar a próxima questão, nunca no meio de uma resposta. Quando ler: ao mexer no limite diário do
Free ou em como o dia é delimitado.
"""

from datetime import UTC, date, datetime, time
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import EventoEstudo, Questao
from aprovaos.dominio.assinatura import UsoDoDia


def uso_do_dia(db: Session, usuario_id: UUID, dia: date) -> UsoDoDia:
    """Conta as respostas do usuário no intervalo `[00:00, 23:59:59.999999]` de `dia`, em UTC.

    Args:
        db: sessão do request (só leitura).
        usuario_id: dono das respostas.
        dia: o dia de referência — sempre "hoje" na chamada real (`dados/base.py::agora_utc`
            já é UTC; quem chama decide o dia, para a função continuar testável sem relógio).

    Returns:
        `UsoDoDia` com `questoes_respondidas` (todo `evento_estudo(tipo="resposta")` do dia) e
        `ineditas_servidas` (o subconjunto cuja `Questao.inedita` é `True`).
    """
    inicio = datetime.combine(dia, time.min, tzinfo=UTC)
    fim = datetime.combine(dia, time.max, tzinfo=UTC)

    consulta_total = select(func.count()).where(
        EventoEstudo.usuario_id == usuario_id,
        EventoEstudo.tipo == "resposta",
        EventoEstudo.ocorrido_em >= inicio,
        EventoEstudo.ocorrido_em <= fim,
    )
    total = db.scalar(consulta_total) or 0

    consulta_ineditas = (
        select(func.count())
        .select_from(EventoEstudo)
        .join(Questao, Questao.id == EventoEstudo.questao_id)
        .where(
            EventoEstudo.usuario_id == usuario_id,
            EventoEstudo.tipo == "resposta",
            EventoEstudo.ocorrido_em >= inicio,
            EventoEstudo.ocorrido_em <= fim,
            Questao.inedita.is_(True),
        )
    )
    ineditas = db.scalar(consulta_ineditas) or 0

    return UsoDoDia(questoes_respondidas=total, ineditas_servidas=ineditas)
