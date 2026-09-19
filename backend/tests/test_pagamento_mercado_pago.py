# O que é: testes red-first do passo 2 do plano `docs/fatias/12-billing.md` —
# `GatewayMercadoPago` (criar assinatura, cancelar, validar e ler webhook) contra um cliente HTTP
# falso, mesmo molde de `_ClienteHttp` em `motor/fontes/cebraspe.py`. Fonte oficial dos endpoints
# e campos: OpenAPI do Mercado Pago (github.com/mercadopago/openapi, `spec3.json` — recurso
# `/preapproval` — e `schemas/webhooks.yaml`, consultados em 19/09/2026 porque a documentação
# interativa em mercadopago.com.br/developers é renderizada em JS). Quando ler: ao mexer em
# `pagamento/mercado_pago.py`.
import hashlib
import hmac
import json
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import pytest

from aprovaos.dominio.erros import AssinaturaWebhookInvalida
from aprovaos.pagamento.gateway import CobrancaCriada
from aprovaos.pagamento.mercado_pago import GatewayMercadoPago

ACCESS_TOKEN = "APP_USR-token-de-teste"
WEBHOOK_SECRET = "segredo-webhook-de-teste"


class _RespostaFalsa:
    def __init__(self, status_code: int, corpo: Any) -> None:
        self.status_code = status_code
        self._corpo = corpo

    def json(self) -> Any:
        return self._corpo


class ClienteHttpFalso:
    """Dublê do `httpx2.Client`: só `post`/`put`, nunca toca a rede."""

    def __init__(self) -> None:
        self.chamadas_post: list[tuple[str, dict[str, Any], dict[str, str]]] = []
        self.chamadas_put: list[tuple[str, dict[str, Any], dict[str, str]]] = []
        self.resposta_post = _RespostaFalsa(
            201, {"id": "preap-123", "init_point": "https://mercadopago.com/checkout/preap-123"}
        )
        self.resposta_put = _RespostaFalsa(200, {"id": "preap-123", "status": "cancelled"})

    def post(
        self, url: str, *, json: Mapping[str, Any], headers: Mapping[str, str]
    ) -> _RespostaFalsa:
        self.chamadas_post.append((url, dict(json), dict(headers)))
        return self.resposta_post

    def put(
        self, url: str, *, json: Mapping[str, Any], headers: Mapping[str, str]
    ) -> _RespostaFalsa:
        self.chamadas_put.append((url, dict(json), dict(headers)))
        return self.resposta_put


def _assinar(corpo: bytes, id_requisicao: str, ts: str, notif_id: str, segredo: str) -> str:
    manifesto = f"id:{notif_id};request-id:{id_requisicao};ts:{ts};"
    v1 = hmac.new(segredo.encode(), manifesto.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"


def test_criar_assinatura_mensal_chama_preapproval_com_os_campos_da_adr_0015() -> None:
    cliente = ClienteHttpFalso()
    gateway = GatewayMercadoPago(cliente, ACCESS_TOKEN, WEBHOOK_SECRET)
    usuario_id = uuid4()

    cobranca = gateway.criar_assinatura(usuario_id, "mensal", "linda@exemplo.com")

    assert cobranca == CobrancaCriada(
        id_externo="preap-123",
        url_pagamento="https://mercadopago.com/checkout/preap-123",
        expira_em=None,
    )
    url, corpo, headers = cliente.chamadas_post[0]
    assert url == "https://api.mercadopago.com/preapproval"
    assert headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"
    assert corpo["payer_email"] == "linda@exemplo.com"
    assert corpo["external_reference"] == str(usuario_id)
    assert corpo["auto_recurring"] == {
        "frequency": 1,
        "frequency_type": "months",
        "transaction_amount": 59.0,
        "currency_id": "BRL",
    }


def test_criar_assinatura_anual_usa_12_meses_e_490() -> None:
    cliente = ClienteHttpFalso()
    gateway = GatewayMercadoPago(cliente, ACCESS_TOKEN, WEBHOOK_SECRET)
    gateway.criar_assinatura(uuid4(), "anual", "linda@exemplo.com")
    _, corpo, _ = cliente.chamadas_post[0]
    assert corpo["auto_recurring"] == {
        "frequency": 12,
        "frequency_type": "months",
        "transaction_amount": 490.0,
        "currency_id": "BRL",
    }


def test_cancelar_faz_put_com_status_cancelled() -> None:
    cliente = ClienteHttpFalso()
    gateway = GatewayMercadoPago(cliente, ACCESS_TOKEN, WEBHOOK_SECRET)
    gateway.cancelar("preap-123")
    url, corpo, headers = cliente.chamadas_put[0]
    assert url == "https://api.mercadopago.com/preapproval/preap-123"
    assert corpo == {"status": "cancelled"}
    assert headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"


def test_ler_evento_assinatura_valida_autorizada() -> None:
    gateway = GatewayMercadoPago(ClienteHttpFalso(), ACCESS_TOKEN, WEBHOOK_SECRET)
    corpo = json.dumps(
        {
            "id": 999,
            "type": "subscription_preapproval",
            "action": "subscription.authorized",
            "data": {"id": "preap-123"},
        }
    ).encode()
    header = _assinar(corpo, "req-1", "1700000000", "999", WEBHOOK_SECRET)

    evento = gateway.ler_evento(corpo, header, "req-1")

    assert evento is not None
    assert evento.tipo == "assinatura_autorizada"
    assert evento.id_externo == "preap-123"
    assert evento.gateway == "mercado_pago"


def test_ler_evento_assinatura_cancelada() -> None:
    gateway = GatewayMercadoPago(ClienteHttpFalso(), ACCESS_TOKEN, WEBHOOK_SECRET)
    corpo = json.dumps(
        {
            "id": 1000,
            "type": "subscription_preapproval",
            "action": "subscription.cancelled",
            "data": {"id": "preap-123"},
        }
    ).encode()
    header = _assinar(corpo, "req-2", "1700000001", "1000", WEBHOOK_SECRET)

    evento = gateway.ler_evento(corpo, header, "req-2")

    assert evento is not None
    assert evento.tipo == "assinatura_cancelada"


def test_ler_evento_tipo_nao_processado_devolve_none_mas_nao_falha() -> None:
    gateway = GatewayMercadoPago(ClienteHttpFalso(), ACCESS_TOKEN, WEBHOOK_SECRET)
    corpo = json.dumps(
        {"id": 1, "type": "payment", "action": "payment.updated", "data": {"id": "pay-1"}}
    ).encode()
    header = _assinar(corpo, "req-3", "1700000002", "1", WEBHOOK_SECRET)

    assert gateway.ler_evento(corpo, header, "req-3") is None


def test_ler_evento_assinatura_adulterada_e_rejeitada() -> None:
    gateway = GatewayMercadoPago(ClienteHttpFalso(), ACCESS_TOKEN, WEBHOOK_SECRET)
    corpo = json.dumps(
        {
            "id": 999,
            "type": "subscription_preapproval",
            "action": "subscription.authorized",
            "data": {"id": "preap-123"},
        }
    ).encode()
    with pytest.raises(AssinaturaWebhookInvalida):
        gateway.ler_evento(corpo, "ts=1700000000,v1=adulterado", "req-1")


def test_ler_evento_segredo_errado_e_rejeitado() -> None:
    gateway = GatewayMercadoPago(ClienteHttpFalso(), ACCESS_TOKEN, WEBHOOK_SECRET)
    corpo = json.dumps(
        {
            "id": 999,
            "type": "subscription_preapproval",
            "action": "subscription.authorized",
            "data": {"id": "preap-123"},
        }
    ).encode()
    header = _assinar(corpo, "req-1", "1700000000", "999", "segredo-errado")
    with pytest.raises(AssinaturaWebhookInvalida):
        gateway.ler_evento(corpo, header, "req-1")


def test_ler_evento_cabecalho_mal_formado_e_rejeitado() -> None:
    gateway = GatewayMercadoPago(ClienteHttpFalso(), ACCESS_TOKEN, WEBHOOK_SECRET)
    with pytest.raises(AssinaturaWebhookInvalida):
        gateway.ler_evento(b"{}", "sem-formato-nenhum", "req-1")
