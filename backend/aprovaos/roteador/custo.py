"""Preços por modelo, câmbio e o registro de uma chamada de LLM (`ChamadaLlm`).

O que é: `PRECOS_USD_POR_MILHAO`, `CAMBIO_BRL_POR_USD`, `estimar_custo_brl` e o modelo Pydantic
`ChamadaLlm` que os agentes entregam ao callback de registro. Quando ler: ao trocar de modelo,
ao atualizar preço/câmbio (fonte única: `docs/06-custos.md`) ou ao gravar uma chamada em `traco`.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

# Preços (entrada, saída) em US$ por 1 milhão de tokens — `docs/06-custos.md` linhas 9–11,
# conferidos em https://ai.google.dev/gemini-api/docs/pricing em 14/09/2026.
PRECOS_USD_POR_MILHAO: dict[str, tuple[Decimal, Decimal]] = {
    "gemini-2.5-flash": (Decimal("0.30"), Decimal("2.50")),
    "gemini-2.5-flash-lite": (Decimal("0.10"), Decimal("0.40")),
}
# Câmbio de referência de `docs/06-custos.md` (R$ 5,40 por US$), o mesmo do orçamento.
CAMBIO_BRL_POR_USD = Decimal("5.40")
_UM_MILHAO = Decimal(1_000_000)
_SEIS_CASAS = Decimal("0.000001")


class ModeloSemPreco(LookupError):
    """O modelo pedido não está em `PRECOS_USD_POR_MILHAO`; sem preço não há estimativa."""


class ChamadaLlm(BaseModel):
    """Uma chamada de LLM concluída (com sucesso ou erro), pronta para virar linha em `traco`.

    Attributes:
        agente: nome do agente que chamou (ex.: `analista-de-edital`).
        modelo: modelo usado (ex.: `gemini-2.5-flash`).
        iniciado_em: instante aware (UTC) em que a chamada começou.
        duracao_ms: duração total em milissegundos.
        tokens_in: tokens do prompt, quando o provedor informou.
        tokens_out: tokens da resposta, quando o provedor informou.
        custo_brl: custo estimado em R$ (`estimar_custo_brl`), ou `None` sem tokens.
        resultado: `ok` ou `erro`.
        erro: nome do tipo da exceção quando `resultado == "erro"` (sem a mensagem).
    """

    agente: str
    modelo: str
    iniciado_em: datetime
    duracao_ms: int
    tokens_in: int | None
    tokens_out: int | None
    custo_brl: Decimal | None
    resultado: Literal["ok", "erro"]
    erro: str | None = None


def estimar_custo_brl(modelo: str, tokens_in: int, tokens_out: int) -> Decimal:
    """Estima o custo de uma chamada em R$, com seis casas decimais.

    Args:
        modelo: chave de `PRECOS_USD_POR_MILHAO`.
        tokens_in: tokens do prompt.
        tokens_out: tokens da resposta.

    Returns:
        `(tokens_in × preço_in + tokens_out × preço_out) / 1M × câmbio`, quantizado em 6 casas.

    Raises:
        ModeloSemPreco: se o modelo não tiver preço tabelado.
    """
    try:
        preco_in, preco_out = PRECOS_USD_POR_MILHAO[modelo]
    except KeyError as erro:
        raise ModeloSemPreco(modelo) from erro
    usd = (Decimal(tokens_in) * preco_in + Decimal(tokens_out) * preco_out) / _UM_MILHAO
    return (usd * CAMBIO_BRL_POR_USD).quantize(_SEIS_CASAS)
