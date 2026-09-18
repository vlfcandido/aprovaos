# O que é: testes do passo 8 da V2 — custo estimado em R$ por modelo, linha em `traco` por chamada
# de LLM, gasto do dia e teto diário. Quando ler: ao mudar preço, câmbio ou a regra do teto.
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Traco
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dados.repositorio_traco import gasto_do_dia, registrar_traco
from aprovaos.dominio.conta import DadosCadastro
from aprovaos.roteador.custo import ChamadaLlm, ModeloSemPreco, estimar_custo_brl
from aprovaos.roteador.teto import TetoDiario

AGORA = datetime(2026, 9, 17, 15, 30, tzinfo=UTC)


def _chamada(
    iniciado_em: datetime = AGORA, custo: Decimal | None = Decimal("0.2052")
) -> ChamadaLlm:
    return ChamadaLlm(
        agente="analista-de-edital",
        modelo="gemini-2.5-flash",
        iniciado_em=iniciado_em,
        duracao_ms=1234,
        tokens_in=60_000,
        tokens_out=8_000,
        custo_brl=custo,
        resultado="ok",
    )


def test_estimar_custo_flash() -> None:
    # 60k × 0,30/M = 0,018 US$; 8k × 2,50/M = 0,020 US$; (0,038) × 5,40 = 0,2052 R$.
    assert estimar_custo_brl("gemini-2.5-flash", 60_000, 8_000) == Decimal("0.205200")


def test_estimar_custo_flash_lite() -> None:
    assert estimar_custo_brl("gemini-2.5-flash-lite", 1_000_000, 0) == Decimal("0.540000")


def test_modelo_sem_preco() -> None:
    with pytest.raises(ModeloSemPreco):
        estimar_custo_brl("gemini-x", 1, 1)


def test_registrar_traco_grava_linha(db: Session) -> None:
    usuario = criar_conta(db, DadosCadastro(email="linda@exemplo.com", senha="12345678"))
    registrar_traco(db, _chamada(), usuario_id=usuario.id)
    db.commit()

    linha = db.scalars(select(Traco)).one()
    assert linha.agente == "analista-de-edital"
    assert linha.modelo == "gemini-2.5-flash"
    assert linha.tokens_in == 60_000
    assert linha.tokens_out == 8_000
    assert linha.custo_brl == Decimal("0.205200")
    assert linha.duracao_ms == 1234
    assert linha.resultado == "ok"
    assert linha.erro is None
    assert linha.usuario_id == usuario.id
    assert linha.iniciado_em == AGORA


def test_registrar_traco_com_erro(db: Session) -> None:
    chamada = _chamada(custo=None).model_copy(update={"resultado": "erro", "erro": "RuntimeError"})
    linha = registrar_traco(db, chamada, usuario_id=None)
    db.commit()
    assert linha.resultado == "erro"
    assert linha.erro == "RuntimeError"
    assert linha.custo_brl is None
    assert linha.usuario_id is None


def test_gasto_do_dia(db: Session) -> None:
    registrar_traco(db, _chamada(AGORA - timedelta(hours=1), Decimal("1.20")), usuario_id=None)
    registrar_traco(db, _chamada(AGORA - timedelta(hours=2), Decimal("0.50")), usuario_id=None)
    registrar_traco(db, _chamada(AGORA - timedelta(days=1), Decimal("9.00")), usuario_id=None)
    registrar_traco(db, _chamada(AGORA - timedelta(minutes=5), None), usuario_id=None)
    db.commit()
    assert gasto_do_dia(db, AGORA) == Decimal("1.70")


def test_gasto_do_dia_sem_linhas(db: Session) -> None:
    assert gasto_do_dia(db, AGORA) == Decimal("0")


def test_teto_diario(db: Session) -> None:
    registrar_traco(db, _chamada(AGORA - timedelta(hours=1), Decimal("1.20")), usuario_id=None)
    registrar_traco(db, _chamada(AGORA - timedelta(hours=2), Decimal("0.50")), usuario_id=None)
    db.commit()
    teto = TetoDiario(limite_brl=Decimal("3.00"))
    assert teto.pode_chamar(db, AGORA) is True

    registrar_traco(db, _chamada(AGORA - timedelta(minutes=1), Decimal("1.40")), usuario_id=None)
    db.commit()
    assert teto.pode_chamar(db, AGORA) is False
    assert TetoDiario(limite_brl=Decimal("0")).pode_chamar(db, AGORA) is False
