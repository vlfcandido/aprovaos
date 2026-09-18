"""Teto diário de gasto com LLM em R$ (ADR-0018: R$ 3/dia; ADR-0030: vale desde a 1ª chamada).

O que é: `TetoDiario.pode_chamar(db, agora)`, que compara o gasto do dia em `traco` com o limite.
Quando ler: antes de criar um agente que chama modelo; quando o DNA sair "por regras" com motivo
"teto diário atingido".
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from aprovaos.dados.repositorio_traco import gasto_do_dia


@dataclass(frozen=True)
class TetoDiario:
    """Limite diário de gasto em R$; `limite_brl = 0` bloqueia toda chamada.

    Attributes:
        limite_brl: gasto máximo do dia (UTC), em R$.
    """

    limite_brl: Decimal

    def pode_chamar(self, db: Session, agora: datetime) -> bool:
        """Diz se ainda há orçamento no dia de `agora` para mais uma chamada.

        Args:
            db: sessão do request (lê `traco`).
            agora: instante aware de referência.

        Returns:
            `True` se `gasto_do_dia(db, agora) < limite_brl`.
        """
        return gasto_do_dia(db, agora) < self.limite_brl
