"""Rotas HTML de questão: `/topico/{slug}/questoes` (ver e responder) e reportar erro.

O que é: `GET /topico/{slug}/questoes` mostra a próxima questão publicável do tópico que o
usuário ainda não respondeu nem reportou (`repositorio_questao.proxima_questao`); `POST` no
mesmo endereço registra a resposta e devolve só o fragmento HTMX com o resultado (decisão 1 do
passo 13); `POST /questoes/{id}/reportar` grava o reporte. O isolamento por tenant é feito aqui:
o `slug` é vocabulário global (compartilhado entre editais), então toda rota amarra o tópico ao
edital de algum concurso do tenant do usuário logado — tópico fora disso é 404 (decisão 2).
Quando ler: ao mexer na tela de resolver questão ou no fluxo de reportar erro.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.api.db import obter_db
from aprovaos.api.sessao import exigir_usuario
from aprovaos.api.templates import renderizar
from aprovaos.dados.modelos import (
    Concurso,
    Edital,
    EventoEstudo,
    Questao,
    ReporteErro,
    Topico,
    TopicoEdital,
    Usuario,
)
from aprovaos.dados.repositorio_questao import (
    proxima_questao,
    registrar_reporte,
    registrar_resposta,
)

router = APIRouter(include_in_schema=False)

#: Valores aceitos para `confianca` (decisão 3: obrigatório antes de responder).
CONFIANCAS_VALIDAS = ("certeza", "duvida")

MENSAGEM_TOPICO_NAO_ENCONTRADO = "Tópico não encontrado nesta conta."
MENSAGEM_CONFIANCA_OBRIGATORIA = "Diga se você tem certeza ou dúvida antes de responder."
MENSAGEM_QUESTAO_NAO_ENCONTRADA = "Questão não encontrada."
MENSAGEM_QUESTAO_INDISPONIVEL = (
    "Esta questão não está mais disponível para responder — atualize a página e tente de novo."
)

RESPOSTA_TEXTO = {"C": "Certo", "E": "Errado"}


def _topico_do_tenant(db: Session, slug: str, tenant_id: UUID) -> Topico | None:
    """Localiza o tópico pelo `slug` só se ele pertencer a um edital de um concurso do tenant.

    O tópico é vocabulário global (`Topico.slug` é único e compartilhado entre editais); a
    junção com `topico_edital` → `edital` → `concurso` é o que restringe "pertence a este
    tenant" — sem ela, qualquer usuário logado poderia ler questões de qualquer edital só
    sabendo o slug.

    Args:
        db: sessão do request.
        slug: slug global do tópico, vindo da URL.
        tenant_id: tenant do usuário logado.

    Returns:
        O `Topico`, ou `None` se nenhum edital do tenant o contiver.
    """
    consulta = (
        select(Topico)
        .join(TopicoEdital, TopicoEdital.topico_id == Topico.id)
        .join(Edital, Edital.id == TopicoEdital.edital_id)
        .join(Concurso, Concurso.id == Edital.concurso_id)
        .where(Topico.slug == slug, Concurso.tenant_id == tenant_id)
    )
    return db.scalars(consulta).first()


def _exigir_topico_do_tenant(db: Session, slug: str, usuario: Usuario) -> Topico:
    """`_topico_do_tenant` obrigatório: sem correspondência, levanta 404 no formato da V1."""
    topico = _topico_do_tenant(db, slug, usuario.tenant_id)
    if topico is None:
        raise HTTPException(status_code=404, detail=MENSAGEM_TOPICO_NAO_ENCONTRADO)
    return topico


def _questao_pendente(
    db: Session, usuario_id: UUID, topico_id: UUID, questao_id: UUID
) -> Questao | None:
    """A `questao_id` só é aceita se ainda está pendente para este usuário neste tópico.

    Existe para a rota nunca gravar `registrar_resposta` contra uma questão que não é a que a
    tela mostrou — um `questao_id` de outro tópico, de uma questão já respondida (corrida entre
    abas, back/refresh) ou já reportada é rejeitado aqui, antes de qualquer gravação.
    `evento_estudo` é append-only e alimenta o FSRS da V5: um evento gravado contra a questão
    errada não tem conserto depois.

    Args:
        db: sessão do request.
        usuario_id: quem está respondendo.
        topico_id: tópico já resolvido para o tenant (da URL).
        questao_id: `questao_id` que veio do formulário.

    Returns:
        A `Questao`, ou `None` se ela não existir, não for deste tópico, não for publicável, ou
        já tiver resposta/reporte deste usuário.
    """
    respondidas = select(EventoEstudo.questao_id).where(
        EventoEstudo.usuario_id == usuario_id, EventoEstudo.tipo == "resposta"
    )
    reportadas = select(ReporteErro.conteudo_id).where(
        ReporteErro.usuario_id == usuario_id, ReporteErro.conteudo_tipo == "questao"
    )
    consulta = select(Questao).where(
        Questao.id == questao_id,
        Questao.topico_id == topico_id,
        Questao.publicavel.is_(True),
        Questao.id.not_in(respondidas),
        Questao.id.not_in(reportadas),
    )
    return db.scalars(consulta).first()


def _contexto_questao(topico: Topico, questao: Questao | None) -> dict[str, object]:
    """Monta o contexto do template `questoes/topico.html`.

    O gabarito nunca entra aqui (decisão 4): só o comando, o texto de apoio, o enunciado e a
    origem completa, todos vindos direto da `questao` — nada de reconstruir a partir de outro
    lugar.

    Args:
        topico: o tópico já resolvido para o tenant.
        questao: a próxima questão publicável, ou `None` sem nenhuma sobrando.

    Returns:
        O contexto para `renderizar`.
    """
    contexto: dict[str, object] = {
        "topico": {"slug": topico.slug, "nome": topico.nome},
        "questao": None,
    }
    if questao is not None:
        origem = questao.origem or {}
        contexto["questao"] = {
            "id": str(questao.id),
            "comando": questao.comando,
            "texto_apoio": questao.texto_apoio,
            "enunciado": questao.enunciado,
        }
        contexto["origem"] = origem
    return contexto


@router.get("/topico/{slug}/questoes")
def obter_questao(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    slug: str,
) -> Response:
    """Mostra a próxima questão publicável do tópico, sem revelar o gabarito.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (só leitura).
        usuario: o usuário logado (sem login, `exigir_usuario` redireciona para `/entrar`).
        slug: slug global do tópico.

    Returns:
        O HTML de `questoes/topico.html`; com `questao=None` no contexto quando não sobra
        nenhuma para este usuário (200, sem erro — decisão 7).

    Raises:
        HTTPException: 404 se o tópico não pertencer a nenhum edital do tenant (decisão 2).
    """
    topico = _exigir_topico_do_tenant(db, slug, usuario)
    questao = proxima_questao(db, usuario.id, topico.id)
    contexto = _contexto_questao(topico, questao)
    return renderizar(request, "questoes/topico.html", contexto, usuario)


@router.post("/topico/{slug}/questoes")
def responder_questao(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    slug: str,
    resposta: Annotated[str, Form()],
    questao_id: Annotated[UUID, Form()],
    confianca: Annotated[str | None, Form()] = None,
    tempo_ms: Annotated[int, Form()] = 0,
) -> Response:
    """Registra a resposta à questão indicada e devolve o fragmento do resultado.

    O `questao_id` é obrigatório e vem de um campo oculto do formulário — a página só o
    preenche com o `id` da questão que ela de fato mostrou. A rota confere de novo que essa
    questão ainda está pendente para este usuário (`_questao_pendente`) antes de gravar
    qualquer coisa: sem essa checagem, duas abas abertas, um back/refresh ou qualquer corrida
    gravariam a resposta contra outra questão, e `evento_estudo` é append-only — não tem
    conserto depois.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        usuario: o usuário logado.
        slug: slug global do tópico.
        resposta: `"C"`/`"E"`, o que o aluno julgou.
        questao_id: `id` da questão respondida, do campo oculto do formulário.
        confianca: `"certeza"`/`"duvida"`; `None` (campo ausente) é erro (decisão 3).
        tempo_ms: tempo gasto na questão, em milissegundos; `0` quando o cliente não manda.

    Returns:
        O fragmento `questoes/_resultado.html` com o gabarito, o acerto e a origem (200).

    Raises:
        HTTPException: 404 se o tópico não pertencer a nenhum edital do tenant, ou se
            `questao_id` não for uma questão pendente deste tópico para este usuário; 400 sem
            `confianca` ou com um valor fora de `CONFIANCAS_VALIDAS`.
    """
    topico = _exigir_topico_do_tenant(db, slug, usuario)
    if confianca not in CONFIANCAS_VALIDAS:
        raise HTTPException(status_code=400, detail=MENSAGEM_CONFIANCA_OBRIGATORIA)

    questao = _questao_pendente(db, usuario.id, topico.id, questao_id)
    if questao is None:
        raise HTTPException(status_code=404, detail=MENSAGEM_QUESTAO_INDISPONIVEL)

    evento = registrar_resposta(db, usuario, questao, resposta, confianca, tempo_ms)
    db.commit()

    contexto = _contexto_questao(topico, questao)
    contexto["evento"] = {
        "acertou": evento.acertou,
        "resposta_texto": RESPOSTA_TEXTO.get(resposta, resposta),
        "gabarito_texto": RESPOSTA_TEXTO.get(questao.gabarito or "", questao.gabarito),
        "justificativa": (
            questao.justificativa_certo if evento.acertou else questao.justificativa_errado
        ),
    }
    return renderizar(request, "questoes/_resultado.html", contexto, usuario)


@router.post("/questoes/{questao_id}/reportar")
def reportar_questao(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    questao_id: UUID,
    motivo: Annotated[str, Form()],
) -> Response:
    """Registra o reporte de erro de uma questão (some da fila só de quem reportou — premissa H).

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        usuario: o usuário logado.
        questao_id: chave da questão reportada.
        motivo: o texto livre do reporte.

    Returns:
        O fragmento `questoes/_reportado.html` confirmando o registro (200).

    Raises:
        HTTPException: 404 se a questão não existir.
    """
    questao = db.get(Questao, questao_id)
    if questao is None:
        raise HTTPException(status_code=404, detail=MENSAGEM_QUESTAO_NAO_ENCONTRADA)
    registrar_reporte(db, usuario, questao, motivo)
    db.commit()
    return renderizar(request, "questoes/_reportado.html", {}, usuario)
