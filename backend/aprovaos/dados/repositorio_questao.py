"""Repositório de questões: grava o que o curador produziu e serve as consultas de estudo.

O que é: `salvar_questoes` (dedup por `hash_dedup`, sem depender de `IntegrityError` para
funcionar), `contagem_por_topico` (quantas publicáveis por tópico de um edital, para o "0 de 36"
da V2 virar contagem real), `proxima_questao` (a próxima publicável de um tópico que o usuário
nunca respondeu nem reportou — premissa H do plano da V3), `registrar_resposta`/
`registrar_reporte` (gravam `evento_estudo`, nunca alteram `questao`) e `topicos_vistos`
(premissa N: tópicos com pelo menos uma resposta do usuário naquele edital). Quando ler: ao
ligar o comando de curadoria (passo 12) ou as rotas de questão (passo 13). Como o repositório da
V2 (`repositorio_edital.py`): funções soltas recebendo `Session` como primeiro parâmetro, fazem
`add`/`flush`; o `commit` é sempre da rota/comando.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import (
    EventoEstudo,
    Questao,
    ReporteErro,
    Topico,
    TopicoEdital,
    Usuario,
)
from aprovaos.dominio.questao import QuestaoCurada


def salvar_questoes(db: Session, questoes: list[QuestaoCurada]) -> tuple[int, int]:
    """Grava as questões curadas que ainda não existem, deduplicando por `hash_dedup`.

    Consulta os hashes já gravados antes de inserir — a função não depende de capturar
    `IntegrityError` para funcionar; a `UNIQUE` de `questao.hash_dedup` é só a rede de segurança
    contra corrida. Rodar a mesma lista duas vezes não cria linha nova: a segunda chamada
    devolve `(0, N)`. Faz `add`/`flush`; quem commita é a rota/comando.

    Args:
        db: sessão do request/comando.
        questoes: a saída do curador (`motor.curadoria.curador.curar`).

    Returns:
        `(quantidade de linhas novas, quantidade de já existentes)`.
    """
    if not questoes:
        return 0, 0

    hashes = [questao.hash_dedup for questao in questoes]
    existentes = set(
        db.scalars(select(Questao.hash_dedup).where(Questao.hash_dedup.in_(hashes))).all()
    )
    slugs = {questao.topico_slug for questao in questoes if questao.topico_slug is not None}
    topicos_por_slug: dict[str, Topico] = {}
    if slugs:
        for encontrado in db.scalars(select(Topico).where(Topico.slug.in_(slugs))).all():
            topicos_por_slug[encontrado.slug] = encontrado

    novas = 0
    repetidas = 0
    for questao in questoes:
        if questao.hash_dedup in existentes:
            repetidas += 1
            continue
        topico: Topico | None = (
            topicos_por_slug.get(questao.topico_slug) if questao.topico_slug else None
        )
        db.add(
            Questao(
                adapter=questao.adapter,
                banca=questao.banca,
                tipo_item=questao.tipo_item,
                comando=questao.comando,
                texto_apoio=questao.texto_apoio,
                texto_apoio_itens=questao.texto_apoio_itens,
                enunciado=questao.enunciado,
                gabarito_preliminar=questao.gabarito_preliminar,
                gabarito=questao.gabarito,
                gabarito_status=questao.gabarito_status,
                publicavel=questao.publicavel,
                motivo_nao_publicavel=questao.motivo_nao_publicavel,
                regra_prova=questao.regra_prova.model_dump(mode="json"),
                topico=topico,
                topico_confianca=questao.topico_confianca,
                topico_evidencia=questao.topico_evidencia,
                origem=questao.origem.model_dump(mode="json"),
                documento_id=UUID(questao.origem.documento_id),
                hash_dedup=questao.hash_dedup,
            )
        )
        existentes.add(questao.hash_dedup)  # evita duplicar dentro da própria lista de entrada
        novas += 1
    db.flush()
    return novas, repetidas


def contagem_por_topico(db: Session, edital_id: UUID) -> dict[UUID, int]:
    """Quantas questões publicáveis existem por tópico deste edital.

    O que fica preso a *este* edital são os **tópicos** considerados — via `TopicoEdital.edital_id`
    — não as questões contadas: `questao.topico_id` não sabe de edital nenhum, então a junção com
    `topico_edital` é o único jeito de restringir "quais tópicos valem aqui". As questões somadas
    são todas as publicáveis daquele `topico_id`, de qualquer documento/prova que as originou —
    `questao` é um pool de conteúdo global (prova pública), compartilhado por qualquer edital que
    reaproveite o mesmo tópico (premissa D: vocabulário global por `slug`). Tópico sem nenhuma
    questão publicável simplesmente não aparece no dicionário — quem exibe decide o que fazer com
    a ausência.

    Args:
        db: sessão do request.
        edital_id: chave do edital.

    Returns:
        `{topico_id: quantidade de questões com publicavel=True}`.
    """
    consulta = (
        select(TopicoEdital.topico_id, Questao.id)
        .join(Questao, Questao.topico_id == TopicoEdital.topico_id)
        .where(TopicoEdital.edital_id == edital_id, Questao.publicavel.is_(True))
    )
    contagem: dict[UUID, int] = {}
    for topico_id, _questao_id in db.execute(consulta).all():
        contagem[topico_id] = contagem.get(topico_id, 0) + 1
    return contagem


def proxima_questao(db: Session, usuario_id: UUID, topico_id: UUID) -> Questao | None:
    """A próxima questão publicável do tópico que este usuário nunca respondeu nem reportou.

    Premissa H: um reporte esconde a questão só para quem reportou, não para os demais alunos —
    por isso o filtro de reporte é por `usuario_id`, igual ao de resposta. A ordem é por
    `criado_em` (com `id` como desempate), nunca aleatória, para o resultado ser reproduzível em
    teste e para as questões mais antigas — em geral as primeiras curadas — saírem primeiro.

    Args:
        db: sessão do request.
        usuario_id: aluno que vai responder.
        topico_id: tópico do vocabulário global.

    Returns:
        A `Questao` mais antiga ainda disponível, ou `None` sem nenhuma sobrando.
    """
    respondidas = select(EventoEstudo.questao_id).where(
        EventoEstudo.usuario_id == usuario_id, EventoEstudo.tipo == "resposta"
    )
    reportadas = select(ReporteErro.conteudo_id).where(
        ReporteErro.usuario_id == usuario_id, ReporteErro.conteudo_tipo == "questao"
    )
    consulta = (
        select(Questao)
        .where(
            Questao.topico_id == topico_id,
            Questao.publicavel.is_(True),
            Questao.id.not_in(respondidas),
            Questao.id.not_in(reportadas),
        )
        .order_by(Questao.criado_em, Questao.id)
    )
    return db.scalars(consulta).first()


def registrar_resposta(
    db: Session,
    usuario: Usuario,
    questao: Questao,
    resposta: str,
    confianca: str,
    tempo_ms: int,
) -> EventoEstudo:
    """Grava a resposta como um `evento_estudo`; nunca altera a `questao` respondida.

    Estatística de acerto (dificuldade/discriminação estimadas) é papel da calibração, fatia
    futura — `evento_estudo` é append-only e é a única fonte da verdade sobre o que o aluno
    respondeu, quando e se acertou.

    Args:
        db: sessão do request.
        usuario: quem respondeu.
        questao: a questão respondida (só para ler o gabarito e o id; não é alterada).
        resposta: o que o aluno marcou (`"C"`/`"E"` nesta fatia).
        confianca: `"certeza"`/`"duvida"`, como o aluno declarou.
        tempo_ms: tempo gasto na questão, em milissegundos.

    Returns:
        O `EventoEstudo` gravado.
    """
    evento = EventoEstudo(
        usuario_id=usuario.id,
        ocorrido_em=agora_utc(),
        tipo="resposta",
        questao_id=questao.id,
        acertou=resposta == questao.gabarito,
        resposta=resposta,
        tempo_ms=tempo_ms,
        confianca_declarada=confianca,
    )
    db.add(evento)
    db.flush()
    return evento


def registrar_reporte(db: Session, usuario: Usuario, questao: Questao, motivo: str) -> ReporteErro:
    """Grava o reporte de erro e o evento correspondente; a questão continua publicada.

    Despublicar por reporte é papel do calibrador (fatia 8) — aqui a questão só some de
    `proxima_questao` para quem reportou (premissa H); os demais alunos continuam recebendo-a.

    Args:
        db: sessão do request.
        usuario: quem reportou.
        questao: a questão reportada.
        motivo: o texto livre do reporte.

    Returns:
        O `ReporteErro` gravado, com `status="aberto"`.
    """
    reporte = ReporteErro(
        usuario_id=usuario.id,
        conteudo_tipo="questao",
        conteudo_id=questao.id,
        motivo=motivo,
        status="aberto",
    )
    db.add(reporte)
    db.add(
        EventoEstudo(
            usuario_id=usuario.id,
            ocorrido_em=agora_utc(),
            tipo="reporte",
            questao_id=questao.id,
        )
    )
    db.flush()
    return reporte


def topicos_vistos(db: Session, usuario_id: UUID, edital_id: UUID) -> set[UUID]:
    """Os tópicos deste edital com pelo menos uma resposta deste usuário (premissa N).

    É o que faz o "0 de 36" da página do concurso (V2) contar de verdade a partir da V3: um
    tópico entra no conjunto assim que o aluno responde à primeira questão dele.

    Args:
        db: sessão do request.
        usuario_id: aluno.
        edital_id: chave do edital (o tópico é vocabulário global; o edital decide quais tópicos
            valem para este conjunto).

    Returns:
        Conjunto de `topico_id`; vazio se nada foi respondido ainda.
    """
    consulta = (
        select(TopicoEdital.topico_id)
        .join(Questao, Questao.topico_id == TopicoEdital.topico_id)
        .join(EventoEstudo, EventoEstudo.questao_id == Questao.id)
        .where(
            TopicoEdital.edital_id == edital_id,
            EventoEstudo.usuario_id == usuario_id,
            EventoEstudo.tipo == "resposta",
        )
        .distinct()
    )
    return set(db.scalars(consulta).all())
