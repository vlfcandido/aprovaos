# O que é: testes red-first do passo 1 do plano `docs/fatias/12-billing.md` — limites do
# Free/Pro e o tier efetivo de uma assinatura (Ruling 47, Ruling 46 §2). Quando ler: antes de
# mexer em `dominio/assinatura.py`.
from datetime import date, timedelta

import pytest

from aprovaos.dominio.assinatura import (
    DIAS_TOLERANCIA_EM_ATRASO,
    LIMITES,
    UsoDoDia,
    calcular_fim_do_periodo,
    pode_criar_edital,
    pode_responder,
    tier_efetivo,
)


def test_limites_free_e_pro_batem_com_a_adr_0015() -> None:
    assert LIMITES["free"].questoes_por_dia == 20
    assert LIMITES["free"].editais_com_dna == 1
    assert LIMITES["pro"].questoes_por_dia is None
    assert LIMITES["pro"].editais_com_dna is None


def test_pode_responder_free_ate_a_vigesima() -> None:
    veredito = pode_responder("free", UsoDoDia(questoes_respondidas=19, ineditas_servidas=0))
    assert veredito.permitido is True
    assert veredito.motivo is None
    assert veredito.convite is None


def test_pode_responder_free_bloqueia_na_vigesima_primeira() -> None:
    veredito = pode_responder("free", UsoDoDia(questoes_respondidas=20, ineditas_servidas=0))
    assert veredito.permitido is False
    assert veredito.motivo is not None and veredito.motivo != ""
    assert veredito.convite is not None and "assine" in veredito.convite.lower()
    assert "ameaç" not in veredito.convite.lower()


def test_pode_responder_pro_nunca_bloqueia() -> None:
    veredito = pode_responder("pro", UsoDoDia(questoes_respondidas=10_000, ineditas_servidas=0))
    assert veredito.permitido is True


def test_pode_criar_edital_free_so_o_primeiro() -> None:
    assert pode_criar_edital("free", 0).permitido is True
    negado = pode_criar_edital("free", 1)
    assert negado.permitido is False
    assert negado.motivo is not None
    assert negado.convite is not None


def test_pode_criar_edital_pro_sem_teto() -> None:
    assert pode_criar_edital("pro", 50).permitido is True


@pytest.mark.parametrize(
    ("status", "dias_apos_fim", "esperado"),
    [
        ("ativa", 0, "pro"),
        ("ativa", 400, "pro"),
        ("cancelada", -1, "pro"),  # ainda dentro do período pago
        ("cancelada", 0, "pro"),  # último dia do período pago
        ("cancelada", 1, "free"),  # período pago já acabou
        ("em_atraso", DIAS_TOLERANCIA_EM_ATRASO - 1, "pro"),  # 9º dia
        ("em_atraso", DIAS_TOLERANCIA_EM_ATRASO, "pro"),  # 10º dia, ainda dentro da janela
        ("em_atraso", DIAS_TOLERANCIA_EM_ATRASO + 1, "free"),  # 11º dia, janela encerrada
        ("expirada", 0, "free"),
        ("expirada", -100, "free"),
    ],
)
def test_tier_efetivo(status: str, dias_apos_fim: int, esperado: str) -> None:
    fim_do_periodo = date(2026, 9, 1)
    hoje = fim_do_periodo + timedelta(days=dias_apos_fim)
    assert tier_efetivo(status, fim_do_periodo, hoje) == esperado  # type: ignore[arg-type]


def test_calcular_fim_do_periodo_mensal() -> None:
    assert calcular_fim_do_periodo("mensal", date(2026, 9, 19)) == date(2026, 10, 19)


def test_calcular_fim_do_periodo_anual() -> None:
    assert calcular_fim_do_periodo("anual", date(2026, 9, 19)) == date(2027, 9, 19)


def test_calcular_fim_do_periodo_ajusta_dia_para_mes_mais_curto() -> None:
    # 31/jan + 1 mês não existe (fevereiro tem, no máximo, 29 dias) — cai no último dia de fev.
    assert calcular_fim_do_periodo("mensal", date(2026, 1, 31)) == date(2026, 2, 28)


# A piloto foi subir um edital em 24/09/2026 e levou "o plano Free processa o DNA de 1
# concurso". O billing nasce DESLIGADO (sem as chaves do Mercado Pago, `/assinar` é 404 e
# ninguém consegue assinar), então o limite do Free virava uma parede sem porta: não havia
# caminho para levantá-lo. Limite que não pode ser levantado não é limite, é defeito.
def test_sem_billing_ativo_nao_ha_limite_de_edital() -> None:
    """Com o billing desligado o produto se comporta como antes de a fatia 12 existir."""
    veredito = pode_criar_edital("free", editais_com_dna_existentes=5, billing_ativo=False)

    assert veredito.permitido is True
    assert veredito.motivo is None


def test_sem_billing_ativo_nao_ha_limite_de_questoes() -> None:
    """Mesma regra para a cota diária de questões — a porta é a mesma."""
    uso = UsoDoDia(questoes_respondidas=9_999, ineditas_servidas=0)
    veredito = pode_responder("free", uso, billing_ativo=False)

    assert veredito.permitido is True


def test_com_billing_ativo_o_limite_do_free_continua_valendo() -> None:
    """Quando existe caminho para assinar, o limite volta a ser limite — a fatia 12 intacta."""
    veredito = pode_criar_edital("free", editais_com_dna_existentes=1, billing_ativo=True)

    assert veredito.permitido is False
    assert veredito.motivo is not None
