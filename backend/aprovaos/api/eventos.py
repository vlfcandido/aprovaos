"""Rota JSON do aviso de distração (`POST /api/distracao`, fatia 8, F3.6/S-05).

O que é: o único endpoint que a ilha de JS `distracao.js` chama — grava
`EventoEstudo(tipo="distracao")` para o bloco em andamento quando a aluna fica tempo demais nele
ou troca de aba. É deliberadamente menor que o `POST /api/eventos` genérico em lote da
arquitetura (§7): esta fatia só precisa de um evento por chamada, sem fila offline nem PWA (isso
entra quando o PWA existir, fase 6/ADR-0013). Sem sessão válida, `401` no formato `{codigo,
mensagem, acao}` — a ilha de JS ignora silenciosamente (degrada sem quebrar, ADR-0019). Quando
ler: ao mexer no aviso de distração ou no que ele grava.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aprovaos.api.db import obter_db
from aprovaos.api.sessao import usuario_atual
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import EventoEstudo, Usuario
from aprovaos.dados.repositorio_plano import buscar_bloco_do_usuario

router = APIRouter(prefix="/api")

MENSAGEM_NAO_AUTENTICADO = "Entre na sua conta para registrar isto."
MENSAGEM_BLOCO_NAO_ENCONTRADO = "Bloco não encontrado."


class DistracaoRecebida(BaseModel):
    """Corpo de `POST /api/distracao` — a ilha de JS manda só o bloco em andamento.

    Attributes:
        bloco_id: o bloco (`Bloco.id`) que estava com `status="iniciado"` no momento do aviso.
    """

    bloco_id: UUID


@router.post("/distracao", status_code=204)
def registrar_distracao(
    corpo: DistracaoRecebida,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario | None, Depends(usuario_atual)],
) -> Response:
    """Grava o evento de distração para o bloco indicado — discreto, sem bloqueio (S-05).

    Args:
        corpo: `{"bloco_id": "..."}`.
        db: sessão de banco do request (o commit é feito aqui).
        usuario: o usuário logado, se houver (`usuario_atual` — nunca redireciona; esta rota é
            JSON, não HTML).

    Returns:
        `204 No Content` — a ilha de JS não lê o corpo da resposta.

    Raises:
        HTTPException: 401 sem sessão válida; 404 se o bloco não pertencer a este usuário.
    """
    if usuario is None:
        raise HTTPException(status_code=401, detail=MENSAGEM_NAO_AUTENTICADO)
    bloco = buscar_bloco_do_usuario(db, usuario.id, corpo.bloco_id)
    if bloco is None:
        raise HTTPException(status_code=404, detail=MENSAGEM_BLOCO_NAO_ENCONTRADO)
    db.add(
        EventoEstudo(
            usuario_id=usuario.id, ocorrido_em=agora_utc(), tipo="distracao", bloco_id=bloco.id
        )
    )
    db.commit()
    return Response(status_code=204)
