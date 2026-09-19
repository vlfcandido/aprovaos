"""Intervalo de Wilson para proporção — a fundação estatística do painel (fatia 10, §2 do plano).

O que é: `Proporcao` (ponto estimado + banda de confiança) e as duas funções puras
`intervalo_wilson` e `sobrepoe`. A partir desta fatia, todo número de proficiência exibido no
painel nasce daqui — nunca do proxy `50/(1+peso)` do diagnóstico (Ruling 35,
`docs/fatias/10-painel.md` §1): aquele proxy mede quanto já perguntamos, não a precisão da
estimativa, e "66,7 % ± 7,14" lido como intervalo é enganoso. Quando ler: antes de adicionar
qualquer número de acerto/erro a uma tela — se ele não passou por `intervalo_wilson`, é suspeito.
"""

import math
from typing import Final

from pydantic import BaseModel

#: `z` da normal padrão para 95 % de confiança — o valor do produto (docs/fatias/10-painel.md §2).
Z_PADRAO: Final = 1.96


class Proporcao(BaseModel):
    """Uma proporção observada com a banda de confiança de Wilson.

    Attributes:
        acertos: quantidade de acertos observados.
        total: quantidade total de observações (sempre `>= 1` — `total == 0` não gera `Proporcao`,
            vira `ValueError` em `intervalo_wilson`).
        pct: ponto estimado `acertos / total * 100`.
        inferior_pct: limite inferior do intervalo de Wilson, grampeado em `[0, 100]`.
        superior_pct: limite superior do intervalo de Wilson, grampeado em `[0, 100]`.
    """

    acertos: int
    total: int
    pct: float
    inferior_pct: float
    superior_pct: float


def _grampear_pct(pct: float) -> float:
    """Confina um percentual a `[0, 100]` — só apresentação, nunca corrige o cálculo estatístico.

    O intervalo de Wilson pode sair de `[0, 100]` por erro de ponto flutuante nas bordas (ex.:
    `intervalo_wilson(0, 10)` dá um inferior da ordem de `-1e-15`; `intervalo_wilson(10, 10)` dá um
    superior de `99,9986`, que fica em `100,0` só depois do grampo). O grampo é documentado aqui
    porque esconder isso dentro da fórmula confundiria "o que o Wilson calculou" com "o que a tela
    pode mostrar sem parecer errado".
    """
    return max(0.0, min(100.0, pct))


def intervalo_wilson(acertos: int, total: int, z: float = Z_PADRAO) -> Proporcao:
    """Calcula o intervalo de Wilson (score interval) para uma proporção binomial.

    Fonte: Wilson, E. B. (1927), *Probable Inference, the Law of Succession, and Statistical
    Inference*, Journal of the American Statistical Association 22(158), 209–212 — o intervalo
    recomendado para proporção com `n` pequeno, ao contrário do intervalo de Wald (que degenera em
    `[0, 0]` quando `acertos == 0`), conforme Brown, L. D.; Cai, T. T.; DasGupta, A. (2001),
    *Interval Estimation for a Binomial Proportion*, Statistical Science 16(2), 101–133.

    Args:
        acertos: quantos acertos foram observados.
        total: quantas observações no total.
        z: escore da normal padrão para o nível de confiança desejado (padrão `1,96`, ≈ 95 %).

    Returns:
        A `Proporcao` com o ponto estimado e a banda, ambos grampeados em `[0, 100]` para
        apresentação.

    Raises:
        ValueError: quando `total <= 0`, `acertos < 0` ou `acertos > total` — nunca devolve um
            intervalo fabricado para um dado inválido (regra 11 do `CLAUDE.md`: lacuna declarada,
            nunca um número por padrão).
    """
    if total <= 0:
        raise ValueError("total deve ser positivo para calcular uma proporção")
    if acertos < 0 or acertos > total:
        raise ValueError("acertos deve estar entre 0 e total")

    p = acertos / total
    z2 = z * z
    denominador = 1 + z2 / total
    centro = p + z2 / (2 * total)
    ajuste = z * math.sqrt(p * (1 - p) / total + z2 / (4 * total**2))
    inferior = (centro - ajuste) / denominador
    superior = (centro + ajuste) / denominador

    return Proporcao(
        acertos=acertos,
        total=total,
        pct=p * 100,
        inferior_pct=_grampear_pct(inferior * 100),
        superior_pct=_grampear_pct(superior * 100),
    )


def sobrepoe(a: Proporcao, b: Proporcao) -> bool:
    """Diz se duas bandas de Wilson se sobrepõem — o critério de "padrão com suporte" do RF-17.

    Args:
        a: uma proporção com banda.
        b: outra proporção com banda.

    Returns:
        `True` quando os intervalos `[a.inferior_pct, a.superior_pct]` e
        `[b.inferior_pct, b.superior_pct]` têm interseção não vazia (inclusive nas bordas);
        simétrico em `a`/`b` — `sobrepoe(a, b) == sobrepoe(b, a)`.
    """
    return a.inferior_pct <= b.superior_pct and b.inferior_pct <= a.superior_pct
