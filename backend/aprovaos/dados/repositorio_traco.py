"""Repositório de `traco`: grava uma linha por chamada de LLM e soma o gasto do dia.

O que é: `registrar_traco(db, chamada, usuario_id)` e `gasto_do_dia(db, agora)`. Quando ler: ao
ligar um agente novo ao roteador ou ao investigar o teto diário. Faz `add`/`flush`; o `commit`
é da rota (convenção transversal).
"""

from datetime import UTC, datetime, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Traco
from aprovaos.roteador.custo import ChamadaLlm


def registrar_traco(db: Session, chamada: ChamadaLlm, usuario_id: UUID | None) -> Traco:
    """Grava a chamada como linha de `traco` (`tier` fica `None` na V2).

    Args:
        db: sessão do request.
        chamada: dados da chamada concluída.
        usuario_id: usuário em nome de quem o agente rodou, se houver.

    Returns:
        A linha `Traco` já com `id` (após `flush`).
    """
    traco = Traco(
        iniciado_em=chamada.iniciado_em,
        duracao_ms=chamada.duracao_ms,
        usuario_id=usuario_id,
        agente=chamada.agente,
        modelo=chamada.modelo,
        tokens_in=chamada.tokens_in,
        tokens_out=chamada.tokens_out,
        custo_brl=chamada.custo_brl,
        resultado=chamada.resultado,
        erro=chamada.erro,
    )
    db.add(traco)
    db.flush()
    return traco


def gasto_do_dia(db: Session, agora: datetime) -> Decimal:
    """Soma `custo_brl` das chamadas iniciadas no dia UTC de `agora` (`None` conta como zero).

    Args:
        db: sessão do request.
        agora: instante aware de referência.

    Returns:
        O total em R$ como `Decimal` (zero sem linhas).
    """
    inicio_do_dia = datetime.combine(agora.astimezone(UTC).date(), time.min, tzinfo=UTC)
    consulta = select(func.coalesce(func.sum(Traco.custo_brl), 0)).where(
        Traco.iniciado_em >= inicio_do_dia
    )
    # `func.sum` herda o tipo `Numeric` da coluna: o resultado já chega como `Decimal`.
    return Decimal(db.scalar(consulta) or 0)
