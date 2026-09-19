"""A implementação real do `GatewayPagamento`: Mercado Pago, recurso `/preapproval` (ADR-0025).

O que é: `GatewayMercadoPago` e `criar_gateway_mercado_pago`/`gateway_pagamento_disponivel`
(ADR-0044 — inerte sem `MERCADO_PAGO_ACCESS_TOKEN`/`_WEBHOOK_SECRET`). Fonte oficial: a
documentação interativa em mercadopago.com.br/developers é renderizada em JS e não expõe o corpo
sem executá-lo, então os endpoints/campos abaixo vêm do **OpenAPI oficial** que o Mercado Pago
mantém em `github.com/mercadopago/openapi` (consultado em 19/09/2026): `spec3.json` (operações
`createSubscription`/`updateSubscription` do recurso `/preapproval`, schemas `SubscriptionRequest`/
`AutoRecurring`/`Subscription`) e `schemas/webhooks.yaml` (`WebhookNotification`,
`WebhookSignatureHeader` — o formato do `x-signature` e o manifesto HMAC).

**Lacunas declaradas** (não inventadas — a fonte acima não fecha estes pontos):
    - `Subscription` não tem campo de expiração para `init_point`; `CobrancaCriada.expira_em`
      sempre `None` para este gateway.
    - o manifesto do HMAC é `"id:[notif_id];request-id:[req_id];ts:[ts];"`; a fonte não deixa
      explícito se `notif_id` é o `id` de topo do webhook ou o `data.id` do recurso — esta
      implementação usa o `id` de topo (o único campo chamado literalmente `id` no schema
      `WebhookNotification`). **Não verificado contra um webhook real** — ADR-0025 já registra
      dois pontos não verificados; este é um terceiro, para o dono confirmar quando ligar a
      credencial de verdade (`docs/PENDENCIAS.md`).
    - webhook de pagamento recusado/em atraso: fora do escopo desta fatia (`pagamento.gateway`).

Quando ler: antes de mexer em criação/cancelamento de assinatura ou na validação do webhook.
"""

import hashlib
import hmac
import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

import httpx2

from aprovaos.config import Configuracoes
from aprovaos.dominio.erros import AssinaturaWebhookInvalida
from aprovaos.pagamento.gateway import CobrancaCriada, EventoPagamento, Periodicidade

BASE_URL = "https://api.mercadopago.com"
URL_PREAPPROVAL = f"{BASE_URL}/preapproval"
URL_PREAPPROVAL_ID = f"{BASE_URL}/preapproval/{{id_externo}}"

#: ADR-0015: R$ 59/mês, R$ 490/ano — já decidido, não repetido aqui como número novo.
PRECOS_BRL: dict[Periodicidade, Decimal] = {"mensal": Decimal("59.00"), "anual": Decimal("490.00")}

#: `AutoRecurring.frequency_type` só aceita `"months"`/`"days"` (não há `"years"`) — anual é
#: cobrado uma vez a cada 12 meses.
FREQUENCIA_MESES: dict[Periodicidade, int] = {"mensal": 1, "anual": 12}

#: Recurso destinado ao produto (ADR-0025: `moeda BRL`, mercado brasileiro).
MOEDA = "BRL"


class _RespostaHttp(Protocol):
    """O subconjunto de `httpx2.Response` que este adapter usa."""

    @property
    def status_code(self) -> int:
        """Código de status HTTP da resposta."""
        ...

    def json(self) -> Any:
        """Devolve o corpo decodificado."""
        ...


class _ClienteHttp(Protocol):
    """O subconjunto de `httpx2.Client` que este adapter usa (mesmo molde de `cebraspe.py`)."""

    def post(
        self, url: str, *, json: Mapping[str, Any], headers: Mapping[str, str]
    ) -> _RespostaHttp:
        """Executa um `POST` com corpo JSON e devolve a resposta."""
        ...

    def put(
        self, url: str, *, json: Mapping[str, Any], headers: Mapping[str, str]
    ) -> _RespostaHttp:
        """Executa um `PUT` com corpo JSON e devolve a resposta."""
        ...


def _montar_manifesto(notif_id: str, id_requisicao: str, ts: str) -> str:
    """Monta o manifesto HMAC exatamente no formato de `schemas/webhooks.yaml` do MP."""
    return f"id:{notif_id};request-id:{id_requisicao};ts:{ts};"


def _extrair_ts_e_v1(assinatura_header: str) -> tuple[str, str]:
    """Separa `ts=<...>,v1=<...>` do `x-signature`; levanta se o formato não bater."""
    partes: dict[str, str] = {}
    for pedaco in assinatura_header.split(","):
        chave, separador, valor = pedaco.strip().partition("=")
        if not separador:
            raise AssinaturaWebhookInvalida("cabeçalho x-signature sem o formato ts=...,v1=...")
        partes[chave] = valor
    if "ts" not in partes or "v1" not in partes:
        raise AssinaturaWebhookInvalida("cabeçalho x-signature sem ts ou v1")
    return partes["ts"], partes["v1"]


class GatewayMercadoPago:
    """Implementação real de `pagamento.gateway.GatewayPagamento` para o Mercado Pago.

    Attributes:
        cliente: cliente HTTP já configurado (real ou falso, injetado — nenhum I/O na criação).
        access_token: `MERCADO_PAGO_ACCESS_TOKEN`, enviado como `Authorization: Bearer`.
        webhook_secret: `MERCADO_PAGO_WEBHOOK_SECRET`, usado só para validar o HMAC do webhook.
    """

    def __init__(self, cliente: _ClienteHttp, access_token: str, webhook_secret: str) -> None:
        """Recebe o cliente HTTP e as duas credenciais; não faz nenhuma chamada de rede aqui."""
        self._cliente = cliente
        self._access_token = access_token
        self._webhook_secret = webhook_secret

    def _cabecalhos(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    def criar_assinatura(
        self, usuario_id: UUID, periodicidade: Periodicidade, email: str
    ) -> CobrancaCriada:
        """Cria a assinatura via `POST /preapproval` (recurso "Subscriptions" do MP).

        Args:
            usuario_id: vira `external_reference`, para casar o webhook com o usuário.
            periodicidade: `"mensal"` ou `"anual"` (ADR-0015: R$ 59 ou R$ 490).
            email: `payer_email` — quem vai autorizar o pagamento.

        Returns:
            `CobrancaCriada` com o `id_externo` e o `init_point` (URL de checkout) da resposta.
        """
        corpo = {
            "reason": f"AprovaOS Pro ({periodicidade})",
            "payer_email": email,
            "external_reference": str(usuario_id),
            "auto_recurring": {
                "frequency": FREQUENCIA_MESES[periodicidade],
                "frequency_type": "months",
                "transaction_amount": float(PRECOS_BRL[periodicidade]),
                "currency_id": MOEDA,
            },
        }
        resposta = self._cliente.post(URL_PREAPPROVAL, json=corpo, headers=self._cabecalhos())
        dados = resposta.json()
        return CobrancaCriada(
            id_externo=dados["id"], url_pagamento=dados["init_point"], expira_em=None
        )

    def cancelar(self, id_externo: str) -> None:
        """Cancela via `PUT /preapproval/{id}` com `{"status": "cancelled"}`."""
        url = URL_PREAPPROVAL_ID.format(id_externo=id_externo)
        self._cliente.put(url, json={"status": "cancelled"}, headers=self._cabecalhos())

    def ler_evento(
        self, corpo: bytes, assinatura_header: str, id_requisicao: str
    ) -> EventoPagamento | None:
        """Valida o `x-signature` (HMAC-SHA256) antes de interpretar o corpo.

        Ver o docstring do módulo para a lacuna declarada sobre qual `id` entra no manifesto.

        Raises:
            AssinaturaWebhookInvalida: cabeçalho mal formado ou HMAC que não confere.
        """
        ts, v1_recebido = _extrair_ts_e_v1(assinatura_header)
        try:
            evento_bruto = json.loads(corpo)
        except (json.JSONDecodeError, UnicodeDecodeError) as erro:
            raise AssinaturaWebhookInvalida(f"corpo do webhook não é JSON válido: {erro}") from erro
        notif_id = str(evento_bruto.get("id", ""))
        manifesto = _montar_manifesto(notif_id, id_requisicao, ts)
        v1_calculado = hmac.new(
            self._webhook_secret.encode(), manifesto.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(v1_calculado, v1_recebido):
            raise AssinaturaWebhookInvalida("HMAC do x-signature não confere")

        tipo = evento_bruto.get("type")
        acao = evento_bruto.get("action")
        id_externo = str(evento_bruto.get("data", {}).get("id", ""))
        if tipo == "subscription_preapproval" and acao == "subscription.authorized":
            return EventoPagamento(
                tipo="assinatura_autorizada", id_externo=id_externo, gateway="mercado_pago"
            )
        if tipo == "subscription_preapproval" and acao == "subscription.cancelled":
            return EventoPagamento(
                tipo="assinatura_cancelada", id_externo=id_externo, gateway="mercado_pago"
            )
        return None


def gateway_pagamento_disponivel(config: Configuracoes) -> bool:
    """`True` só com as duas credenciais configuradas (Ruling 46: nascem e morrem juntas)."""
    return (
        config.mercado_pago_access_token is not None
        and config.mercado_pago_webhook_secret is not None
    )


def criar_gateway_mercado_pago(config: Configuracoes) -> GatewayMercadoPago:
    """Fábrica: monta o `httpx2.Client` real e devolve o gateway pronto para uso.

    Nenhum I/O acontece na importação deste módulo — só nesta chamada explícita, e só quando
    `gateway_pagamento_disponivel(config)` já for `True`.

    Args:
        config: configurações do backend.

    Returns:
        Um `GatewayMercadoPago` com cliente HTTP real (timeout de 15s).

    Raises:
        AssertionError: se chamada sem as duas credenciais (bug de quem chama, não do usuário).
    """
    assert config.mercado_pago_access_token is not None
    assert config.mercado_pago_webhook_secret is not None
    cliente = httpx2.Client(timeout=15)
    return GatewayMercadoPago(
        cliente,
        config.mercado_pago_access_token.get_secret_value(),
        config.mercado_pago_webhook_secret.get_secret_value(),
    )
