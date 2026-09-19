"""Revisão espaçada com FSRS: serialização do `fsrs.Card`, o proxy de rating e o texto do cartão.

O que é: `EstadoCartaoFsrs` (os oito campos que a tabela `cartao` grava — os seis do modelo de
dados mais `estado_fsrs`/`passo_fsrs`, adendo à ADR-0022 explicado em
`docs/fatias/V4-revisao-espacada.md` §2), `revisar` (aplica uma revisão — cria o estado do zero
quando ainda não existe) e `montar_frente_verso` (o texto do cartão a partir dos campos de uma
questão, sem depender do ORM). Puro: nenhuma chamada a `datetime.now`; `agora` sempre vem de
fora, de `dados/base.py::agora_utc`. Quando ler: ao mexer no cálculo de agenda de revisão, no
mapeamento de resposta→rating, ou ao investigar por que um cartão venceu num dia inesperado.
"""

from datetime import datetime
from typing import Literal

import fsrs
from pydantic import BaseModel

#: `card_id` fixo passado ao `fsrs.Card()` — o identificador interno do fsrs nunca é lido pelo
#: AprovaOS (a chave é `cartao.id`, um UUID à parte); fixá-lo evita o efeito colateral de
#: `Card()` sem argumento (`time.sleep(0.001)` + `datetime.now()` para gerar um id "único").
_CARD_ID_FIXO = 0

Confianca = Literal["certeza", "duvida"]

#: Mensagem do verso quando a questão não tem gabarito (anulada/sem entrada) — nunca inventa uma
#: letra.
_MENSAGEM_SEM_GABARITO = "Gabarito não disponível para esta questão."


class EstadoCartaoFsrs(BaseModel):
    """O estado do FSRS serializado nas colunas de `cartao`.

    Os seis primeiros atributos são os nomeados em `docs/04-modelo-de-dados.md` §2; os dois
    últimos são o adendo à ADR-0022 (`docs/DECISOES.md`): sem eles, reconstruir o `fsrs.Card`
    perde a fase de aprendizado e recalcula um `due` diferente do real (provado em
    `tests/test_dominio_revisao.py::test_ida_e_volta_sem_perder_estado_fsrs`).

    Attributes:
        stability: `fsrs.Card.stability` — `None` só no instante `card_id` novo sem revisão
            nenhuma (não acontece aqui: `revisar` sempre aplica ao menos uma revisão).
        difficulty: `fsrs.Card.difficulty`.
        due: `fsrs.Card.due` — a agenda; um cartão está vencido quando `due <= agora`.
        last_review: `fsrs.Card.last_review`.
        reps: quantas vezes este cartão já foi revisado. Contador do AprovaOS — esta versão do
            `fsrs.Card` não o mantém (achado do adendo).
        lapses: quantas vezes uma revisão errou um cartão que já estava em `fsrs.State.Review`
            (um esquecimento de algo que já tinha sido aprendido; a primeira vez, quando o
            cartão nasce do erro, não conta — ele nunca tinha sido aprendido).
        estado_fsrs: `fsrs.State` (`Learning=1`, `Review=2`, `Relearning=3`).
        passo_fsrs: `fsrs.Card.step` — `None` quando o cartão já saiu da fase de aprendizado.
    """

    stability: float | None
    difficulty: float | None
    due: datetime
    last_review: datetime | None
    reps: int
    lapses: int
    estado_fsrs: int
    passo_fsrs: int | None


def rating_por_resposta(acertou: bool, confianca: Confianca) -> fsrs.Rating:
    """Traduz acertou/confiança no rating do FSRS — o proxy da §3 do plano V4.

    Args:
        acertou: se a resposta bateu com o gabarito.
        confianca: `"certeza"`/`"duvida"`, o mesmo campo que a tela de questão já coleta.

    Returns:
        `Rating.Again` quando errou (não importa a confiança — errar é errar); `Rating.Easy`
        quando acertou com certeza; `Rating.Good` quando acertou em dúvida. `Rating.Hard` nunca
        é devolvido nesta fatia: exigiria um sinal de "acertei, mas com dificuldade" que a tela
        não coleta.
    """
    if not acertou:
        return fsrs.Rating.Again
    return fsrs.Rating.Easy if confianca == "certeza" else fsrs.Rating.Good


def _card_de_estado(estado: EstadoCartaoFsrs | None, agora: datetime) -> fsrs.Card:
    """Reconstrói o `fsrs.Card`; um cartão novo quando `estado` é `None`.

    Args:
        estado: o estado gravado, ou `None` para o primeiro erro que faz o cartão nascer.
        agora: só usado como `due` do cartão novo — irrelevante para o cálculo da próxima
            revisão (o `fsrs.Scheduler` decide a partir de `last_review`, nunca de `due`), mas
            evita que `fsrs.Card()` chame `datetime.now()` por conta própria.

    Returns:
        O `fsrs.Card` pronto para `Scheduler.review_card`.
    """
    if estado is None:
        return fsrs.Card(card_id=_CARD_ID_FIXO, due=agora)
    return fsrs.Card(
        card_id=_CARD_ID_FIXO,
        state=fsrs.State(estado.estado_fsrs),
        step=estado.passo_fsrs,
        stability=estado.stability,
        difficulty=estado.difficulty,
        due=estado.due,
        last_review=estado.last_review,
    )


def revisar(
    estado_atual: EstadoCartaoFsrs | None,
    *,
    acertou: bool,
    confianca: Confianca,
    agora: datetime,
) -> EstadoCartaoFsrs:
    """Aplica uma revisão do FSRS; cria o estado inicial quando `estado_atual` é `None`.

    É a mesma função para as duas situações do plano V4: "nasce" (chamada com `estado_atual =
    None` no momento do erro que cria o cartão) e "se atualiza" (chamada com o estado gravado, em
    qualquer revisão seguinte, na tela de estudo ou na tela de revisão).

    Args:
        estado_atual: o estado gravado em `cartao`, ou `None` no primeiro erro.
        acertou: se a resposta desta revisão bateu com o gabarito.
        confianca: `"certeza"`/`"duvida"` declarada antes de responder.
        agora: instante da revisão, sempre `datetime` aware em UTC (`dados/base.py::agora_utc`).

    Returns:
        O novo `EstadoCartaoFsrs`, pronto para gravar em `cartao`.
    """
    card = _card_de_estado(estado_atual, agora)
    estava_aprendido = card.state == fsrs.State.Review
    rating = rating_por_resposta(acertou, confianca)
    novo_card, _log = fsrs.Scheduler().review_card(card, rating, review_datetime=agora)

    reps_anterior = estado_atual.reps if estado_atual is not None else 0
    lapses_anterior = estado_atual.lapses if estado_atual is not None else 0
    esqueceu = (not acertou) and estava_aprendido

    return EstadoCartaoFsrs(
        stability=novo_card.stability,
        difficulty=novo_card.difficulty,
        due=novo_card.due,
        last_review=novo_card.last_review,
        reps=reps_anterior + 1,
        lapses=lapses_anterior + (1 if esqueceu else 0),
        estado_fsrs=novo_card.state.value,
        passo_fsrs=novo_card.step,
    )


def montar_frente_verso(
    *, comando: str | None, enunciado: str, gabarito: str | None
) -> tuple[str, str]:
    """Monta `cartao.frente`/`cartao.verso` a partir dos campos de uma questão.

    Recebe os campos já lidos (nunca o modelo ORM: o domínio não depende de `dados/`) —
    `dados/repositorio_cartao.py` passa `questao.comando`/`questao.enunciado`/`questao.gabarito`.
    O texto é só o resumo que identifica o cartão fora do contexto da questão (ex.: numa lista);
    a tela de revisão de um cartão ligado a uma questão mostra a questão de novo, não este texto
    (decisão do plano V4 §5 — "não duplique a tela").

    Args:
        comando: `Questao.comando`, quando existe.
        enunciado: `Questao.enunciado`.
        gabarito: `Questao.gabarito`; `None` quando a questão está anulada ou sem entrada no
            gabarito.

    Returns:
        `(frente, verso)`; o verso nunca inventa uma letra quando `gabarito` é `None`.
    """
    frente = f"{comando}\n\n{enunciado}" if comando else enunciado
    verso = f"Gabarito: {gabarito}" if gabarito else _MENSAGEM_SEM_GABARITO
    return frente, verso
