"""Gateway de pagamento (ADR-0025, fatia 12): a interface e a implementação Mercado Pago.

O que é: pacote `pagamento/` — `gateway.py` (o `Protocol` `GatewayPagamento` e os modelos
`CobrancaCriada`/`EventoPagamento` da fronteira) e `mercado_pago.py` (a implementação real,
inerte sem `MERCADO_PAGO_ACCESS_TOKEN`/`_WEBHOOK_SECRET`, ADR-0044). Quando ler: antes de mexer em
qualquer coisa que crie, cancele ou receba webhook de assinatura.
"""
