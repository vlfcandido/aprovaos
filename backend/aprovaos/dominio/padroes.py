"""Detecção de padrões de erro com suporte estatístico mínimo (RF-17) — fatia 10 §4 do plano.

O que é: `RespostaClassificada` (o que a detecção precisa de cada resposta já classificada) e
`PadraoErro`, mais a função pura `detectar_padroes`. O critério de "padrão" não é um limiar
arbitrário de diferença: um cruzamento só vira padrão quando tem `n >= MINIMO_RESPOSTAS_PADRAO`
**e** sua banda de Wilson (`dominio/estatistica.py`) não se sobrepõe à da linha de base — sem
sobreposição a diferença é defensável, com sobreposição é ruído e não aparece. Isso cumpre
literalmente o CA "só mostra padrão com suporte estatístico mínimo". `"materia"` e `"topico"` são
dimensões distintas e nunca se confundem: matéria vem de `materia`, tópico vem de `topico_nome`
(`questao.topico_id` → `topico`) — rotular um agrupamento por matéria como `"topico"` seria "dado
errado com cara de certo" (ADR-0036), a classe de defeito mais cara deste projeto. Quando ler: ao
mudar o piso de suporte, as faixas de horário ou o texto da frase exibida.
Plano: `docs/fatias/10-painel.md` §4.
"""

from collections.abc import Callable
from typing import Final, Literal

from pydantic import BaseModel

from aprovaos.dominio.estatistica import Proporcao, intervalo_wilson, sobrepoe

Dimensao = Literal["materia", "topico", "banca", "horario", "energia"]

#: Piso de suporte estatístico (RF-17 "definir n"): abaixo disso o cruzamento nem é avaliado.
MINIMO_RESPOSTAS_PADRAO: Final = 8


class RespostaClassificada(BaseModel):
    """Uma resposta já classificada nas cinco dimensões que `detectar_padroes` cruza.

    Attributes:
        acertou: se a resposta foi certa.
        materia: a matéria do tópico respondido — é o que a dimensão `"materia"` agrupa.
        topico_nome: o nome do tópico respondido (`topico.nome`, via `questao.topico_id`) — é o
            que a dimensão `"topico"` agrupa; nunca confundido com `materia` (mais de um tópico
            cabe na mesma matéria).
        banca: a banca da questão (`questao.banca`).
        hora_local: a hora do dia (0–23) já convertida para `America/Sao_Paulo` (Ruling 37,
            fora deste módulo).
        energia: a energia declarada no check-in (1–5), ou `None` quando não foi informada — não
            entra na dimensão `"energia"` (não vira "energia desconhecida" com cara de padrão).
    """

    acertou: bool
    materia: str
    topico_nome: str
    banca: str
    hora_local: int
    energia: int | None


class PadraoErro(BaseModel):
    """Um padrão de erro/acerto com suporte estatístico (banda de Wilson sem sobreposição).

    Attributes:
        dimensao: em qual das cinco dimensões o padrão apareceu.
        valor: o rótulo do subgrupo ("Direito Administrativo" em `"materia"`, "Improbidade
            Administrativa" em `"topico"`, "CESPE/Cebraspe" em `"banca"`, "madrugada" em
            `"horario"`, "energia 2" em `"energia"`).
        proporcao: a banda de Wilson do subgrupo.
        base: a banda de Wilson da linha de base (todas as respostas recebidas).
        frase: o texto pronto para a tela, já com os números.
    """

    dimensao: Dimensao
    valor: str
    proporcao: Proporcao
    base: Proporcao
    frase: str


def _faixa_horario(hora_local: int) -> str:
    """Mapeia a hora (0–23) para uma das quatro faixas fixas ditas na tela (§4 do plano)."""
    if hora_local <= 5:
        return "madrugada"
    if hora_local <= 11:
        return "manhã"
    if hora_local <= 17:
        return "tarde"
    return "noite"


def _agrupar(
    respostas: list[RespostaClassificada],
    dimensao: Dimensao,
    valor_de: Callable[[RespostaClassificada], str | None],
) -> list[tuple[Dimensao, str, list[RespostaClassificada]]]:
    """Agrupa as respostas por `valor_de(resposta)`, descartando quem devolve `None`.

    `None` é o caso de energia não declarada: essa resposta continua contando para a linha de
    base e para as outras dimensões, mas não gera nem alimenta nenhum grupo de energia.
    """
    grupos: dict[str, list[RespostaClassificada]] = {}
    for resposta in respostas:
        chave = valor_de(resposta)
        if chave is None:
            continue
        grupos.setdefault(chave, []).append(resposta)
    return [(dimensao, valor, subgrupo) for valor, subgrupo in grupos.items()]


def _rotulo(dimensao: Dimensao, valor: str) -> str:
    """A preposição certa para a frase, por dimensão ("de madrugada", "com energia 2", ...)."""
    if dimensao == "horario":
        return f"de {valor}"
    if dimensao == "energia":
        return f"com {valor}"
    return f"em {valor}"


def _frase(dimensao: Dimensao, valor: str, proporcao: Proporcao, base: Proporcao) -> str:
    """Monta a frase da tela: "você erra mais de madrugada: 40 % (n=12) contra 72 % no geral"."""
    verbo = "erra mais" if proporcao.pct < base.pct else "acerta mais"
    rotulo = _rotulo(dimensao, valor)
    return (
        f"você {verbo} {rotulo}: {proporcao.pct:.0f} % (n={proporcao.total}) "
        f"contra {base.pct:.0f} % no geral"
    )


def detectar_padroes(respostas: list[RespostaClassificada]) -> list[PadraoErro]:
    """Cruza o histórico nas cinco dimensões e devolve só os cruzamentos com suporte estatístico.

    `"materia"` e `"topico"` são cruzamentos separados e nunca se misturam: o mesmo suporte
    estatístico e o mesmo critério de sobreposição valem para as cinco dimensões — nenhuma delas
    tem piso ou tolerância diferente para "aparecer mais fácil".

    Args:
        respostas: o histórico já classificado
            (`dados/repositorio_painel.py::respostas_classificadas`, fora deste módulo).

    Returns:
        Os `PadraoErro` encontrados, ordenados pela maior diferença entre o ponto estimado do
        subgrupo e o da linha de base (desempate pelo maior `n`); lista vazia quando não há
        resposta nenhuma ou quando nenhum cruzamento passa no piso de suporte
        (`MINIMO_RESPOSTAS_PADRAO`) e na ausência de sobreposição de Wilson.
    """
    if not respostas:
        return []

    total_geral = len(respostas)
    acertos_geral = sum(1 for resposta in respostas if resposta.acertou)
    base = intervalo_wilson(acertos_geral, total_geral)

    candidatos: list[tuple[Dimensao, str, list[RespostaClassificada]]] = []
    candidatos += _agrupar(respostas, "materia", lambda r: r.materia)
    candidatos += _agrupar(respostas, "topico", lambda r: r.topico_nome)
    candidatos += _agrupar(respostas, "banca", lambda r: r.banca)
    candidatos += _agrupar(respostas, "horario", lambda r: _faixa_horario(r.hora_local))
    candidatos += _agrupar(
        respostas, "energia", lambda r: f"energia {r.energia}" if r.energia is not None else None
    )

    padroes: list[PadraoErro] = []
    for dimensao, valor, subgrupo in candidatos:
        total = len(subgrupo)
        if total < MINIMO_RESPOSTAS_PADRAO:
            continue
        acertos = sum(1 for resposta in subgrupo if resposta.acertou)
        proporcao = intervalo_wilson(acertos, total)
        if sobrepoe(proporcao, base):
            continue
        padroes.append(
            PadraoErro(
                dimensao=dimensao,
                valor=valor,
                proporcao=proporcao,
                base=base,
                frase=_frase(dimensao, valor, proporcao, base),
            )
        )

    padroes.sort(key=lambda p: (-abs(p.proporcao.pct - p.base.pct), -p.proporcao.total))
    return padroes
