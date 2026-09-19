"""Rota HTML do plano do dia (`/hoje`, fatia 8, F3.x): plano, check-in, ações de bloco, discordar.

O que é: `GET /hoje` gera (ou obtém, idempotente) o plano de hoje e mostra os blocos com o
porquê; `POST /hoje/checkin` reescreve o plano (energia/sono/tempo reais, ou "hoje quero
descansar") como a próxima versão do mesmo dia; `POST /hoje/bloco/{id}/iniciar|concluir|pular`
registra a ação; `POST /hoje/bloco/{id}/discordar` troca o bloco por outra alternativa (F3.3/
F3.4), sempre respondendo com o impacto em uma frase. Mesmo padrão de `api/rotina.py`: toda
rota devolve a página inteira (`hoje/pagina.html`), e os formulários usam `hx-select="#conteudo"`
para o htmx trocar só o miolo — nenhuma rota de fragmento separada. Sem rotina configurada ou sem
concurso principal/edital (`SemConcursoPrincipal`), a página mostra a mensagem com o link certo
(`/rotina` ou `/editais/subir`), 200, nunca uma exceção estourada. `plano.dias_para_prova`
(RF-19, fatia 10 §7) é recalculado a cada exibição a partir de `perfil_estudo.data_alvo` — nunca
gravado — e liga o selo "Semana da prova" no template quando `plano.modo == "semana_prova"`.
Quando ler: ao mexer na tela "Hoje" ou no fluxo de check-in/discordar.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from sqlalchemy.orm import Session

from aprovaos.api.db import obter_db
from aprovaos.api.sessao import exigir_usuario
from aprovaos.api.templates import renderizar
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Bloco, PlanoDia, Topico, Usuario
from aprovaos.dados.repositorio_plano import (
    buscar_bloco_do_usuario,
    concluir_bloco,
    dias_para_prova_do_dia,
    discordar_bloco,
    gerar_ou_obter_plano_noturno,
    iniciar_bloco,
    pular_bloco,
    registrar_checkin,
)
from aprovaos.dominio.erros import SemConcursoPrincipal
from aprovaos.dominio.plano import MOTIVOS_DISCORDAR

router = APIRouter(include_in_schema=False)

MENSAGEM_ENERGIA_INVALIDA = "Energia precisa ser um número de 1 a 5."
MENSAGEM_MOTIVO_INVALIDO = "Escolha um dos motivos para discordar."
MENSAGEM_BLOCO_NAO_ENCONTRADO = "Bloco não encontrado."

_CHAVES_MOTIVOS_VALIDAS = {chave for chave, _ in MOTIVOS_DISCORDAR}

#: Rota de conteúdo real de cada tipo de bloco — "Iniciar" marca o estado; abrir o conteúdo é
#: navegar para a tela que já existe (aula, questões, revisão), nunca uma tela nova por bloco.
_LINK_POR_TIPO = {"revisao": "/revisar"}


def _link_do_bloco(bloco: Bloco, topico: Topico | None) -> str | None:
    """A URL de conteúdo deste bloco, quando existe (aula/questões apontam pro tópico)."""
    if bloco.tipo == "revisao":
        return _LINK_POR_TIPO["revisao"]
    if topico is None:
        return None
    if bloco.tipo == "aula":
        return f"/topico/{topico.slug}/aula"
    if bloco.tipo == "questoes":
        return f"/topico/{topico.slug}/questoes"
    return None


def _contexto_bloco(db: Session, bloco: Bloco) -> dict[str, object]:
    """Monta o contexto de exibição de um bloco (tipo, tópico, horário, porquê, status, link)."""
    topico = db.get(Topico, bloco.topico_id) if bloco.topico_id is not None else None
    return {
        "id": str(bloco.id),
        "ordem": bloco.ordem,
        "tipo": bloco.tipo,
        "topico_nome": topico.nome if topico is not None else None,
        "materia": topico.materia if topico is not None else None,
        "duracao_min": bloco.duracao_min,
        "hora_sugerida": (
            bloco.hora_sugerida.strftime("%H:%M") if bloco.hora_sugerida is not None else None
        ),
        "porque": bloco.porque,
        "status": bloco.status,
        "link": _link_do_bloco(bloco, topico),
        # Só preenchido quando iniciado — a ilha `distracao.js` usa isto para saber há quanto
        # tempo o bloco está em andamento; `None` (bloco pendente/concluído) desliga o aviso.
        "iniciado_em": bloco.iniciado_em.isoformat() if bloco.iniciado_em is not None else None,
    }


def _contexto_pagina(db: Session, plano: PlanoDia) -> dict[str, object]:
    """Monta o contexto completo de `hoje/pagina.html` a partir de um `PlanoDia` já gravado."""
    blocos_ativos = sorted(
        (b for b in plano.blocos if b.status != "trocado"), key=lambda b: b.ordem
    )
    return {
        "sem_rotina": False,
        "plano": {
            "data": plano.data.isoformat(),
            "versao": plano.versao,
            "modo": plano.modo,
            "tempo_min": plano.tempo_min,
            "porque_geral": plano.porque_geral,
            "energia": plano.energia,
            "sono_h": plano.sono_h,
            # De exibição (RF-19, fatia 10 §7) — o selo "Semana da prova" some quando não há
            # `data_alvo`; recalculado aqui, não gravado em `plano_dia` (P-55: sem tabela nova).
            "dias_para_prova": dias_para_prova_do_dia(db, plano.usuario_id, plano.data),
        },
        "blocos": [_contexto_bloco(db, b) for b in blocos_ativos],
        "motivos_discordar": MOTIVOS_DISCORDAR,
    }


def _pagina_sem_rotina(request: Request, usuario: Usuario, motivo: str) -> Response:
    """A página quando `SemConcursoPrincipal` impede montar o plano (onboarding incompleto)."""
    return renderizar(request, "hoje/pagina.html", {"sem_rotina": True, "motivo": motivo}, usuario)


def _pagina_do_plano(
    request: Request, db: Session, usuario: Usuario, plano: PlanoDia, impacto: str | None = None
) -> Response:
    """A página com o plano já gravado — `impacto` é a frase de "Discordar" (F3.4), quando há."""
    contexto = _contexto_pagina(db, plano)
    if impacto is not None:
        contexto["impacto"] = impacto
    return renderizar(request, "hoje/pagina.html", contexto, usuario)


@router.get("/hoje")
def hoje(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
) -> Response:
    """Gera (ou obtém, idempotente) o plano de hoje e mostra os blocos.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (grava a versão 1 na primeira visita do dia).
        usuario: o usuário logado (sem login, `exigir_usuario` redireciona para `/entrar`).

    Returns:
        `hoje/pagina.html`, sempre 200: com o plano, ou com `sem_rotina=True` e o motivo quando
        falta rotina/concurso principal.
    """
    dia = agora_utc().date()
    try:
        plano = gerar_ou_obter_plano_noturno(db, usuario, dia)
        db.commit()
    except SemConcursoPrincipal as erro:
        db.rollback()
        return _pagina_sem_rotina(request, usuario, str(erro))
    return _pagina_do_plano(request, db, usuario, plano)


@router.post("/hoje/checkin")
def checkin(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    energia: Annotated[int, Form()],
    sono_h: Annotated[float, Form()],
    tempo_min: Annotated[int, Form()],
    quero_descansar: Annotated[str | None, Form()] = None,
) -> Response:
    """Reescreve o plano de hoje com os valores reais do check-in (F3.2).

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        usuario: o usuário logado.
        energia: `1`–`5`.
        sono_h: horas de sono.
        tempo_min: minutos reais disponíveis hoje.
        quero_descansar: `"on"` quando o botão "Hoje quero descansar" foi marcado; `None` senão.

    Returns:
        `hoje/pagina.html` com a nova versão do plano.

    Raises:
        HTTPException: 400 se `energia` estiver fora de `1`–`5`.
    """
    if not 1 <= energia <= 5:
        raise HTTPException(status_code=400, detail=MENSAGEM_ENERGIA_INVALIDA)

    dia = agora_utc().date()
    try:
        plano = registrar_checkin(
            db, usuario, dia, energia, sono_h, tempo_min, quero_descansar == "on"
        )
        db.commit()
    except SemConcursoPrincipal as erro:
        db.rollback()
        return _pagina_sem_rotina(request, usuario, str(erro))
    return _pagina_do_plano(request, db, usuario, plano)


def _exigir_bloco(db: Session, usuario: Usuario, bloco_id: UUID) -> Bloco:
    """`buscar_bloco_do_usuario` obrigatório: sem correspondência, levanta 404."""
    bloco = buscar_bloco_do_usuario(db, usuario.id, bloco_id)
    if bloco is None:
        raise HTTPException(status_code=404, detail=MENSAGEM_BLOCO_NAO_ENCONTRADO)
    return bloco


@router.post("/hoje/bloco/{bloco_id}/iniciar")
def iniciar(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    bloco_id: UUID,
) -> Response:
    """Marca o bloco como iniciado (`EventoEstudo(tipo="bloco_iniciado")`)."""
    bloco = _exigir_bloco(db, usuario, bloco_id)
    iniciar_bloco(db, usuario, bloco, agora_utc())
    db.commit()
    plano = db.get(PlanoDia, bloco.plano_dia_id)
    assert plano is not None  # veio de um bloco já confirmado como do usuário
    return _pagina_do_plano(request, db, usuario, plano)


@router.post("/hoje/bloco/{bloco_id}/concluir")
def concluir(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    bloco_id: UUID,
) -> Response:
    """Marca o bloco como concluído (`EventoEstudo(tipo="bloco_concluido")`)."""
    bloco = _exigir_bloco(db, usuario, bloco_id)
    concluir_bloco(db, usuario, bloco, agora_utc())
    db.commit()
    plano = db.get(PlanoDia, bloco.plano_dia_id)
    assert plano is not None
    return _pagina_do_plano(request, db, usuario, plano)


@router.post("/hoje/bloco/{bloco_id}/pular")
def pular(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    bloco_id: UUID,
) -> Response:
    """Marca o bloco como pulado (`EventoEstudo(tipo="bloco_pulado")`) — nunca quebra o plano."""
    bloco = _exigir_bloco(db, usuario, bloco_id)
    pular_bloco(db, usuario, bloco, agora_utc())
    db.commit()
    plano = db.get(PlanoDia, bloco.plano_dia_id)
    assert plano is not None
    impacto = "Bloco pulado — o resto do dia continua igual."
    return _pagina_do_plano(request, db, usuario, plano, impacto=impacto)


@router.post("/hoje/bloco/{bloco_id}/discordar")
def discordar(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    bloco_id: UUID,
    motivo: Annotated[str, Form()],
) -> Response:
    """Troca o bloco por outra alternativa, com o motivo registrado como evento (F3.3/F3.4).

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        usuario: o usuário logado.
        bloco_id: o bloco que a aluna quer trocar.
        motivo: uma das chaves de `dominio.plano.MOTIVOS_DISCORDAR`.

    Returns:
        `hoje/pagina.html` com o bloco trocado (ou mantido, com o aviso) e o impacto em uma
        frase.

    Raises:
        HTTPException: 404 se o bloco não for deste usuário; 400 se `motivo` não for uma das
            opções válidas.
    """
    if motivo not in _CHAVES_MOTIVOS_VALIDAS:
        raise HTTPException(status_code=400, detail=MENSAGEM_MOTIVO_INVALIDO)
    bloco = _exigir_bloco(db, usuario, bloco_id)
    bloco_novo, _evento = discordar_bloco(db, usuario, bloco, motivo, agora_utc())
    db.commit()
    plano = db.get(PlanoDia, bloco.plano_dia_id)
    assert plano is not None
    if bloco_novo is not None:
        impacto = f"Troquei o bloco: agora é {bloco_novo.tipo}, no mesmo horário."
    else:
        impacto = "Não achei outra opção que coubesse agora — o bloco continua como estava."
    return _pagina_do_plano(request, db, usuario, plano, impacto=impacto)
