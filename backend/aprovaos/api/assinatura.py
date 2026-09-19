"""Rotas de billing (fatia 12, RF-22, Rulings 46-48): assinar, webhook e cancelar.

O que é: `GET/POST /assinar` (planos e criação da assinatura no gateway), `POST
/webhooks/pagamento` (valida a assinatura HMAC antes de olhar o corpo, grava o evento cru e
atualiza a assinatura) e `POST /assinatura/cancelar` (um clique — o Pro continua valendo até o
fim do período pago, `dominio.assinatura.tier_efetivo`). Sem `MERCADO_PAGO_ACCESS_TOKEN`/
`_WEBHOOK_SECRET` (`app.state.gateway_pagamento is None`), as três rotas devolvem 404 e nenhuma
tela de assinatura aparece (Ruling 46) — o produto roda como hoje, todo mundo no Free. Quando
ler: ao mexer no fluxo de assinar, cancelar ou no webhook do gateway de pagamento.
"""

import json
from typing import Annotated, get_args

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from sqlalchemy.orm import Session

from aprovaos.api.db import obter_db
from aprovaos.api.sessao import exigir_usuario
from aprovaos.api.templates import renderizar, responder_redirecionamento
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Usuario
from aprovaos.dados.repositorio_assinatura import (
    aplicar_evento,
    assinatura_do_usuario,
    cancelar_assinatura,
    criar_ou_atualizar_pendente,
)
from aprovaos.dominio.assinatura import Periodicidade
from aprovaos.dominio.erros import AssinaturaWebhookInvalida
from aprovaos.pagamento.gateway import GatewayPagamento
from aprovaos.pagamento.mercado_pago import PRECOS_BRL

router = APIRouter(include_in_schema=False)

MENSAGEM_PERIODICIDADE_INVALIDA = "Periodicidade inválida — escolha mensal ou anual."
MENSAGEM_SEM_ASSINATURA = "Você ainda não tem uma assinatura para cancelar."

#: `Periodicidade` é `Literal["mensal", "anual"]` — os dois valores aceitos no formulário.
PERIODICIDADES_VALIDAS: tuple[str, ...] = get_args(Periodicidade)


def exigir_gateway(request: Request) -> GatewayPagamento:
    """Dependência: `app.state.gateway_pagamento`; 404 sem credencial (Ruling 46).

    Entra **antes** de `exigir_usuario` na assinatura das rotas — sem gateway configurado, a
    rota é 404 mesmo sem login (o produto se comporta como se ela não existisse).
    """
    gateway: GatewayPagamento | None = request.app.state.gateway_pagamento
    if gateway is None:
        raise HTTPException(status_code=404)
    return gateway


@router.get("/assinar")
def tela_assinar(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    gateway: Annotated[GatewayPagamento, Depends(exigir_gateway)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
) -> Response:
    """Mostra os dois planos (ADR-0015) e o que muda entre Free e Pro.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (só leitura).
        gateway: `app.state.gateway_pagamento` (`exigir_gateway` já garantiu que não é `None`).
        usuario: o usuário logado (sem login, `exigir_usuario` redireciona para `/entrar`).

    Returns:
        `conta/assinar.html` com os preços.

    Raises:
        HTTPException: 404 sem gateway configurado.
    """
    assinatura = assinatura_do_usuario(db, usuario.id)
    contexto = {
        "preco_mensal": f"{PRECOS_BRL['mensal']:.2f}".replace(".", ","),
        "preco_anual": f"{PRECOS_BRL['anual']:.2f}".replace(".", ","),
        "assinatura": assinatura,
    }
    return renderizar(request, "conta/assinar.html", contexto, usuario)


@router.post("/assinar")
def assinar(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    gateway: Annotated[GatewayPagamento, Depends(exigir_gateway)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    periodicidade: Annotated[str, Form()],
) -> Response:
    """Cria a assinatura no gateway e redireciona para o checkout.

    A assinatura gravada aqui **ainda não vale como Pro** — só o webhook confirmado
    (`POST /webhooks/pagamento`) faz isso (Ruling 46; `dados.repositorio_assinatura
    .criar_ou_atualizar_pendente`).

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        gateway: `app.state.gateway_pagamento` (`exigir_gateway` já garantiu que não é `None`).
        usuario: o usuário logado.
        periodicidade: `"mensal"` ou `"anual"`, do formulário.

    Returns:
        Redirecionamento 303 para a URL de checkout do gateway.

    Raises:
        HTTPException: 404 sem gateway configurado; 400 com `periodicidade` inválida.
    """
    if periodicidade not in PERIODICIDADES_VALIDAS:
        raise HTTPException(status_code=400, detail=MENSAGEM_PERIODICIDADE_INVALIDA)

    cobranca = gateway.criar_assinatura(usuario.id, periodicidade, usuario.email)  # type: ignore[arg-type]
    agora = agora_utc()
    criar_ou_atualizar_pendente(db, usuario, periodicidade, cobranca.id_externo, agora)  # type: ignore[arg-type]
    db.commit()
    return Response(status_code=303, headers={"Location": cobranca.url_pagamento})


@router.post("/webhooks/pagamento")
async def webhook_pagamento(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    gateway: Annotated[GatewayPagamento, Depends(exigir_gateway)],
) -> Response:
    """Valida o `x-signature` antes de olhar o corpo, grava o evento e atualiza a assinatura.

    Sem sessão de usuário — quem chama é o gateway, não o navegador. A assinatura HMAC é a única
    prova de identidade aceita (regra do produto: webhook sem essa checagem é um endpoint que
    qualquer um usa para liberar Pro de graça).

    Args:
        request: a requisição atual (corpo bruto e cabeçalhos `x-signature`/`x-request-id`).
        db: sessão de banco do request (o commit é feito aqui).
        gateway: `app.state.gateway_pagamento` (`exigir_gateway` já garantiu que não é `None`).

    Returns:
        `200` sempre que a assinatura confere — mesmo para um tipo de evento não reconhecido
        (grava o payload cru e não faz mais nada).

    Raises:
        HTTPException: 404 sem gateway configurado; 400 com assinatura que não confere (nada é
            gravado nesse caso).
    """
    corpo = await request.body()
    assinatura_header = request.headers.get("x-signature", "")
    id_requisicao = request.headers.get("x-request-id", "")
    try:
        evento = gateway.ler_evento(corpo, assinatura_header, id_requisicao)
    except AssinaturaWebhookInvalida as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro

    payload = json.loads(corpo)
    aplicar_evento(db, evento, payload, agora_utc())
    db.commit()
    return Response(status_code=200)


@router.post("/assinatura/cancelar")
def cancelar(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    gateway: Annotated[GatewayPagamento, Depends(exigir_gateway)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
) -> Response:
    """Cancela em um clique: o Pro continua valendo até o fim do período pago.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        gateway: `app.state.gateway_pagamento` (`exigir_gateway` já garantiu que não é `None`).
        usuario: o usuário logado.

    Returns:
        Redirecionamento para `/conta`.

    Raises:
        HTTPException: 404 sem gateway configurado, ou sem assinatura nenhuma para cancelar.
    """
    assinatura = assinatura_do_usuario(db, usuario.id)
    if assinatura is None:
        raise HTTPException(status_code=404, detail=MENSAGEM_SEM_ASSINATURA)

    gateway.cancelar(assinatura.id_externo)
    cancelar_assinatura(db, assinatura, agora_utc())
    db.commit()
    return responder_redirecionamento(request, "/conta")
