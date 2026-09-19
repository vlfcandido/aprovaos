"""Repositório do calibrador (fatia 11): monta a entrada de `dominio/calibracao` e grava a saída.

O que é: `respostas_da_janela`/`reportes_da_janela` (leem `evento_estudo`/`reporte_erro` desde uma
data, já no formato cru que `dominio.calibracao.agregar_metricas` espera),
`origem_por_questao`/`dificuldade_atual_por_questao` (o contexto de cada questão que o domínio
puro não sabe buscar sozinho) e `gravar_calibracao` (insere `Calibracao` e atualiza `Questao`
conforme a `acao` — é aqui que a P-34 se fecha: `despublicar` grava `despublicada_em`, o carimbo
que toda consulta de servir conteúdo passa a filtrar). Quem decide o que fazer com o relatório é
`motor/calibrar.py`; este módulo só lê e grava. Quando ler: ao ligar o comando do calibrador ou ao
investigar por que uma questão despublicada continua/não continua na tela.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Calibracao, EventoEstudo, Questao, ReporteErro
from aprovaos.dominio.calibracao import AjusteCalibracao, Origem, ReporteBruto, RespostaBruta


def respostas_da_janela(db: Session, desde: datetime) -> list[RespostaBruta]:
    """As respostas (`evento_estudo` tipo `resposta`) de qualquer questão, a partir de `desde`.

    Args:
        db: sessão do comando.
        desde: início da janela (`agora_utc() - timedelta(dias=N)`, decidido por quem chama).

    Returns:
        Uma `RespostaBruta` por `evento_estudo`; vazio sem eventos na janela. Eventos de outro
        tipo (`checkin`, `reporte`, etc.) nunca entram aqui.
    """
    consulta = select(EventoEstudo).where(
        EventoEstudo.tipo == "resposta",
        EventoEstudo.ocorrido_em >= desde,
        EventoEstudo.questao_id.is_not(None),
    )
    respostas: list[RespostaBruta] = []
    for evento in db.scalars(consulta).all():
        assert evento.questao_id is not None  # filtrado na consulta; só documenta a garantia
        respostas.append(
            RespostaBruta(
                questao_id=evento.questao_id,
                usuario_id=evento.usuario_id,
                acertou=bool(evento.acertou),
                tempo_ms=evento.tempo_ms,
                confianca_declarada=evento.confianca_declarada,
            )
        )
    return respostas


def reportes_da_janela(db: Session, desde: datetime) -> list[ReporteBruto]:
    """Os reportes de erro (`reporte_erro`, `conteudo_tipo="questao"`) criados a partir de `desde`.

    Todo reporte da janela entra, independentemente do `status` — a skill classifica pelo texto
    do `motivo`, não pelo estado da fila (um reporte "aberto" ontem já é sinal tão válido quanto
    um "em análise" hoje).

    Args:
        db: sessão do comando.
        desde: início da janela.

    Returns:
        Um `ReporteBruto` por reporte; vazio sem reportes na janela.
    """
    consulta = select(ReporteErro).where(
        ReporteErro.conteudo_tipo == "questao", ReporteErro.criado_em >= desde
    )
    return [
        ReporteBruto(questao_id=reporte.conteudo_id, motivo=reporte.motivo)
        for reporte in db.scalars(consulta).all()
    ]


def origem_por_questao(db: Session, questao_ids: list[UUID]) -> dict[UUID, Origem]:
    """`{questao_id: "original"|"inedita"}` a partir de `Questao.inedita`.

    Args:
        db: sessão do comando.
        questao_ids: as questões a resolver.

    Returns:
        Um dicionário com uma entrada por `questao_id` encontrado; ids inexistentes não aparecem.
    """
    if not questao_ids:
        return {}
    consulta = select(Questao.id, Questao.inedita).where(Questao.id.in_(questao_ids))
    return {
        questao_id: ("inedita" if inedita else "original")
        for questao_id, inedita in db.execute(consulta).all()
    }


def dificuldade_atual_por_questao(db: Session, questao_ids: list[UUID]) -> dict[UUID, float]:
    """`{questao_id: dificuldade_est}` só para quem já tem estimativa gravada.

    Nunca inventa `0.0`/`0.5` para quem não tem — a ausência no dicionário é o sinal de "sem
    estimativa anterior" que `dominio.calibracao.MetricasQuestao.dificuldade_est=None` espera.

    Args:
        db: sessão do comando.
        questao_ids: as questões a resolver.

    Returns:
        Um dicionário só com as questões que têm `dificuldade_est` não nulo.
    """
    if not questao_ids:
        return {}
    consulta = select(Questao.id, Questao.dificuldade_est).where(
        Questao.id.in_(questao_ids), Questao.dificuldade_est.is_not(None)
    )
    return {
        questao_id: dificuldade
        for questao_id, dificuldade in db.execute(consulta).all()
        if dificuldade is not None
    }


def gravar_calibracao(db: Session, ajustes: list[AjusteCalibracao], *, data: date) -> None:
    """Insere uma `Calibracao` por ajuste e atualiza a `Questao` conforme a `acao`.

    `manter` só grava a linha histórica, não toca a questão. `ajustar`/`despublicar` também
    atualizam `questao.dificuldade_est`/`discriminacao_est` (regras R-4/R-5/R-6/R-7 sempre trazem
    uma estimativa melhor que a anterior). Só `despublicar` grava `despublicada_em`/`publicada` —
    é o que fecha a P-34: a partir daqui, `despublicada_em` deixa de ser sempre `None`. `sinalizar`
    não muda nada na `Questao` (a fila humana decide depois; sinalizar não é despublicar).

    Args:
        db: sessão do comando.
        ajustes: a saída de `dominio.calibracao.avaliar_questao` para o lote.
        data: o dia da rodada (`calibracao.data`).
    """
    if not ajustes:
        return
    questoes = {
        questao.id: questao
        for questao in db.scalars(
            select(Questao).where(Questao.id.in_([ajuste.questao_id for ajuste in ajustes]))
        ).all()
    }
    for ajuste in ajustes:
        discriminacao_numerica = (
            ajuste.discriminacao if isinstance(ajuste.discriminacao, float) else None
        )
        db.add(
            Calibracao(
                questao_id=ajuste.questao_id,
                data=data,
                dificuldade_real=ajuste.dificuldade_real,
                discriminacao=discriminacao_numerica,
                n=ajuste.n,
                acao=ajuste.acao,
            )
        )
        questao = questoes.get(ajuste.questao_id)
        if questao is None:
            continue
        if ajuste.acao in ("ajustar", "despublicar"):
            questao.dificuldade_est = ajuste.dificuldade_real
            if discriminacao_numerica is not None:
                questao.discriminacao_est = discriminacao_numerica
        if ajuste.acao == "despublicar":
            questao.despublicada_em = agora_utc()
            questao.publicada = False
    db.flush()
