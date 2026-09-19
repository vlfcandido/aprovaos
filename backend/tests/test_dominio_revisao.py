# O que é: testes do passo 1 da V4 — `dominio/revisao.py` (serialização do `fsrs.Card`, o proxy
# de rating e o texto do cartão). Prova a ida e volta com valores reais da biblioteca (sem mock,
# ver plano `docs/fatias/V4-revisao-espacada.md` §2): sem `estado_fsrs`/`passo_fsrs`, duas
# revisões seguidas divergem de verdade no `due` calculado. Quando ler: ao mexer no cálculo de
# agenda de revisão.
from datetime import UTC, datetime, timedelta

import fsrs
import pytest

from aprovaos.dominio.revisao import (
    Confianca,
    EstadoCartaoFsrs,
    montar_frente_verso,
    rating_por_resposta,
    revisar,
)

AGORA = datetime(2026, 1, 1, tzinfo=UTC)
DEZ_MIN_DEPOIS = AGORA + timedelta(minutes=10)


def test_revisar_cria_estado_quando_nao_existe() -> None:
    estado = revisar(None, acertou=False, confianca="duvida", agora=AGORA)
    assert estado.reps == 1
    assert estado.lapses == 0  # primeiro erro nunca é "esquecimento" — o cartão acabou de nascer
    assert estado.last_review == AGORA
    assert estado.due >= AGORA
    assert estado.estado_fsrs == fsrs.State.Learning.value


@pytest.mark.parametrize(
    ("acertou", "confianca", "rating_esperado"),
    [
        (False, "duvida", fsrs.Rating.Again),
        (False, "certeza", fsrs.Rating.Again),
        (True, "duvida", fsrs.Rating.Good),
        (True, "certeza", fsrs.Rating.Easy),
    ],
)
def test_rating_por_resposta(
    acertou: bool, confianca: Confianca, rating_esperado: fsrs.Rating
) -> None:
    assert rating_por_resposta(acertou, confianca) is rating_esperado


def test_ida_e_volta_sem_perder_estado_fsrs() -> None:
    """Reconstruir o `Card` sem `state`/`passo_fsrs` recalcula um `due` diferente do real.

    Duas revisões `Good` seguidas: uma vez passando o `EstadoCartaoFsrs` completo entre as duas
    chamadas (o que `dados/repositorio_cartao.py` faz de verdade), outra vez com uma cópia sem
    `estado_fsrs`/`passo_fsrs` (simulando quem ignorasse o adendo da ADR-0022). Os dois `due`
    finais têm de ser diferentes — é a prova de que os dois campos extras não são cosméticos.
    """
    primeiro = revisar(None, acertou=True, confianca="duvida", agora=AGORA)

    completo = revisar(primeiro, acertou=True, confianca="duvida", agora=DEZ_MIN_DEPOIS)

    incompleto_inicial = EstadoCartaoFsrs(
        stability=primeiro.stability,
        difficulty=primeiro.difficulty,
        due=primeiro.due,
        last_review=primeiro.last_review,
        reps=primeiro.reps,
        lapses=primeiro.lapses,
        estado_fsrs=fsrs.State.Learning.value,
        passo_fsrs=None,  # o dado que se perderia sem o adendo
    )
    incompleto = revisar(incompleto_inicial, acertou=True, confianca="duvida", agora=DEZ_MIN_DEPOIS)

    assert completo.due != incompleto.due


def test_lapses_so_conta_esquecimento_depois_de_aprendido() -> None:
    estado = revisar(None, acertou=True, confianca="certeza", agora=AGORA)
    agora = AGORA
    # revisa "Easy" repetidas vezes, com o tempo suficiente para o fsrs promover o cartão a
    # State.Review (deixar de ser um cartão novo) — 40 dias é generoso para os parâmetros padrão.
    for _ in range(4):
        agora = agora + timedelta(days=10)
        estado = revisar(estado, acertou=True, confianca="certeza", agora=agora)
    assert estado.estado_fsrs == fsrs.State.Review.value
    assert estado.lapses == 0

    agora = agora + timedelta(days=10)
    estado = revisar(estado, acertou=False, confianca="duvida", agora=agora)
    assert estado.lapses == 1


def test_montar_frente_verso_com_comando() -> None:
    frente, verso = montar_frente_verso(
        comando="Julgue o item.", enunciado="O prazo é de 5 dias.", gabarito="C"
    )
    assert "Julgue o item." in frente
    assert "O prazo é de 5 dias." in frente
    assert "C" in verso


def test_montar_frente_verso_sem_gabarito() -> None:
    _frente, verso = montar_frente_verso(comando=None, enunciado="Item anulado.", gabarito=None)
    assert "não disponível" in verso.lower()
