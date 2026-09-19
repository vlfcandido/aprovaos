# O que é: dublê de `GatewayPagamento` para os testes de rota (`test_rota_assinatura.py`) e para
# a execução real sem credencial (`docs/fatias/12-execucao.md` §6) — implementa o mesmo Protocol
# de `pagamento/gateway.py`, nunca toca rede (mesmo molde de `ProvedorGoogleFalso` em
# `test_rota_conta_google.py`). Quando ler: ao escrever teste de `/assinar`,
# `/webhooks/pagamento` ou `/assinatura/cancelar`.
import json
from uuid import UUID

from aprovaos.dominio.erros import AssinaturaWebhookInvalida
from aprovaos.pagamento.gateway import CobrancaCriada, EventoPagamento, Periodicidade

#: A assinatura falsa que `webhook_assinado_falso` produz e que `GatewayPagamentoFalso.ler_evento`
#: aceita — não é HMAC de verdade, só o suficiente para o teste provar que a validação acontece
#: antes do corpo ser interpretado.
ASSINATURA_HEADER_VALIDA = "assinatura-de-teste-valida"


def webhook_assinado_falso(tipo: str, id_externo: str) -> bytes:
    """Monta o corpo JSON de um webhook simulado, no vocabulário que `ler_evento` já traduz."""
    return json.dumps({"tipo": tipo, "id_externo": id_externo}).encode()


class GatewayPagamentoFalso:
    """Dublê determinístico: um `id_externo` novo por assinatura criada, nunca toca rede."""

    def __init__(self) -> None:
        self.criadas: list[tuple[UUID, Periodicidade, str]] = []
        self.canceladas: list[str] = []
        self._contador = 0

    def criar_assinatura(
        self, usuario_id: UUID, periodicidade: Periodicidade, email: str
    ) -> CobrancaCriada:
        """Devolve uma `CobrancaCriada` com `id_externo` sequencial (`falso-1`, `falso-2`, ...)."""
        self._contador += 1
        id_externo = f"falso-{self._contador}"
        self.criadas.append((usuario_id, periodicidade, email))
        return CobrancaCriada(
            id_externo=id_externo,
            url_pagamento=f"https://pagamento.falso.exemplo/{id_externo}",
            expira_em=None,
        )

    def cancelar(self, id_externo: str) -> None:
        """Só registra a chamada — o dublê não tem estado de assinatura do lado do "gateway"."""
        self.canceladas.append(id_externo)

    def ler_evento(
        self, corpo: bytes, assinatura_header: str, id_requisicao: str
    ) -> EventoPagamento | None:
        """Aceita só `ASSINATURA_HEADER_VALIDA`; o corpo é `{"tipo": ..., "id_externo": ...}`."""
        if assinatura_header != ASSINATURA_HEADER_VALIDA:
            raise AssinaturaWebhookInvalida("assinatura falsa não confere")
        dados = json.loads(corpo)
        if dados["tipo"] not in ("assinatura_autorizada", "assinatura_cancelada"):
            return None
        return EventoPagamento(tipo=dados["tipo"], id_externo=dados["id_externo"], gateway="falso")
