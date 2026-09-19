"""Interface de gateway de pagamento (ADR-0025) e os modelos Pydantic da fronteira com ele.

O que é: `GatewayPagamento` (`Protocol` — criar assinatura, cancelar, ler webhook),
`CobrancaCriada` e `EventoPagamento`. Nenhuma implementação concreta mora aqui: a real é
`pagamento.mercado_pago.GatewayMercadoPago` (ADR-0044, inerte sem credencial); a falsa, usada nos
testes e na execução real sem credencial (`docs/fatias/12-execucao.md` §6), é
`tests/dubles_pagamento.py` — mesmo molde de `motor/fontes/cebraspe.py::_ClienteHttp`: código de
produção só fala com o `Protocol`, nunca com uma classe concreta. Quando ler: antes de mexer em
qualquer coisa que crie, cancele ou receba webhook de assinatura.
"""

from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel

from aprovaos.dominio.assinatura import Periodicidade

__all__ = [
    "CobrancaCriada",
    "EventoPagamento",
    "GatewayPagamento",
    "Periodicidade",
    "TipoEventoPagamento",
]

#: Vocabulário do produto para o que um webhook de assinatura pode significar — nunca o
#: vocabulário cru do gateway (`WebhookNotification.action`/`type` do Mercado Pago); é
#: `pagamento.mercado_pago` que traduz um para o outro. Só os dois eventos que a execução real
#: desta fatia cobre (assinar, cancelar — plano §6); pagamento recusado/em atraso fica para uma
#: fatia futura mapear contra um webhook de verdade (`docs/PENDENCIAS.md`) — `tier_efetivo`
#: (`dominio/assinatura.py`) já sabe tratar `status="em_atraso"` no domínio, só falta o produtor.
TipoEventoPagamento = Literal["assinatura_autorizada", "assinatura_cancelada"]


class CobrancaCriada(BaseModel):
    """O que o gateway devolve ao criar uma assinatura — a URL para o pagador confirmar.

    Attributes:
        id_externo: identidade da assinatura no gateway (`assinatura.id_externo`).
        url_pagamento: para onde redirecionar o pagador (checkout do gateway).
        expira_em: até quando `url_pagamento` vale; `None` quando o gateway não declara uma
            expiração — o recurso `/preapproval` do Mercado Pago (fonte abaixo) não tem esse
            campo na resposta, então `GatewayMercadoPago` sempre devolve `None` aqui (lacuna
            declarada, não inventada; `docs/PENDENCIAS.md`).
    """

    id_externo: str
    url_pagamento: str
    expira_em: datetime | None = None


class EventoPagamento(BaseModel):
    """Um evento de webhook validado e traduzido (o corpo cru vai para `evento_cobranca.payload`).

    Attributes:
        tipo: o que aconteceu, no vocabulário do produto — nunca o vocabulário cru do gateway.
        id_externo: a assinatura afetada, no gateway (`assinatura.id_externo`).
        gateway: quem mandou (`"mercado_pago"` — hoje o único).
    """

    tipo: TipoEventoPagamento
    id_externo: str
    gateway: str


class GatewayPagamento(Protocol):
    """O que qualquer gateway de pagamento precisa saber fazer (ADR-0025).

    Real: `pagamento.mercado_pago.GatewayMercadoPago`. Falso: `tests/dubles_pagamento.py`.
    """

    def criar_assinatura(
        self, usuario_id: UUID, periodicidade: Periodicidade, email: str
    ) -> CobrancaCriada:
        """Cria a assinatura no gateway e devolve para onde redirecionar o pagador.

        Args:
            usuario_id: dono da assinatura (`assinatura.usuario_id`; vira `external_reference`
                no Mercado Pago, para casar o webhook com o usuário sem outra consulta).
            periodicidade: `"mensal"` (R$ 59) ou `"anual"` (R$ 490) — ADR-0015.
            email: e-mail do pagador (`Usuario.email`).

        Returns:
            A `CobrancaCriada` com a URL de checkout.
        """
        ...

    def cancelar(self, id_externo: str) -> None:
        """Cancela a assinatura no gateway; idempotente (cancelar a já cancelada não é erro).

        Args:
            id_externo: `assinatura.id_externo` a cancelar.
        """
        ...

    def ler_evento(
        self, corpo: bytes, assinatura_header: str, id_requisicao: str
    ) -> EventoPagamento | None:
        """Valida a assinatura HMAC do webhook e só então interpreta o corpo.

        A validação acontece **antes** de qualquer decisão sobre o corpo — webhook sem essa
        checagem é um endpoint que qualquer um usa para liberar Pro de graça, o defeito que esta
        função existe para não ter.

        Args:
            corpo: o corpo bruto (bytes) da requisição do webhook.
            assinatura_header: o cabeçalho `x-signature` da requisição, cru.
            id_requisicao: o cabeçalho `x-request-id` da requisição, cru (entra no HMAC junto com
                o corpo — ver `pagamento.mercado_pago` para a fonte oficial do formato).

        Returns:
            O `EventoPagamento` traduzido; `None` quando a assinatura confere mas o evento não é
            um dos dois que esta fatia processa (ex.: uma notificação de pagamento avulso) — a
            rota grava o payload cru em `evento_cobranca` mesmo assim, sem mais nenhuma ação.

        Raises:
            AssinaturaWebhookInvalida: a assinatura não confere.
        """
        ...
