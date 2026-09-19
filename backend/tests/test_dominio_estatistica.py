# O que é: testes de `dominio/estatistica.py` — o intervalo de Wilson (fatia 10, §2 do plano
# `docs/fatias/10-painel.md`), fundação de todo número de proficiência do painel (Ruling 35).
# Valores conferidos à mão no brief da fatia. Quando ler: ao mudar a fórmula de Wilson ou o
# critério de sobreposição de bandas.
import pytest

from aprovaos.dominio.estatistica import intervalo_wilson, sobrepoe


def test_caso_do_ruling_35_dois_de_tres() -> None:
    proporcao = intervalo_wilson(2, 3)
    assert proporcao.pct == pytest.approx(66.67, abs=0.01)
    assert proporcao.inferior_pct == pytest.approx(20.7655, abs=0.001)
    assert proporcao.superior_pct == pytest.approx(93.851, abs=0.001)


def test_zero_acertos_nunca_da_intervalo_degenerado() -> None:
    proporcao = intervalo_wilson(0, 10)
    assert proporcao.pct == 0.0
    assert proporcao.inferior_pct == 0.0  # grampeado; sem grampo seria ~-1e-15 (defeito do Wald)
    assert proporcao.superior_pct == pytest.approx(27.754, abs=0.001)


def test_todos_acertos_e_grampeado_em_cem() -> None:
    proporcao = intervalo_wilson(10, 10)
    assert proporcao.inferior_pct == pytest.approx(72.246, abs=0.001)
    assert proporcao.superior_pct == 100.0  # valor exato é 99,9986; grampeado (nunca > 100)


def test_mais_amostra_estreita_a_banda_no_mesmo_ponto() -> None:
    banda_larga = intervalo_wilson(5, 10)
    banda_estreita = intervalo_wilson(50, 100)
    assert banda_larga.pct == banda_estreita.pct == 50.0
    largura_larga = banda_larga.superior_pct - banda_larga.inferior_pct
    largura_estreita = banda_estreita.superior_pct - banda_estreita.inferior_pct
    assert largura_estreita < largura_larga


def test_total_zero_e_erro_nunca_intervalo_por_padrao() -> None:
    with pytest.raises(ValueError):
        intervalo_wilson(0, 0)


def test_acertos_maior_que_total_e_erro() -> None:
    with pytest.raises(ValueError):
        intervalo_wilson(11, 10)


def test_acertos_negativo_e_erro() -> None:
    with pytest.raises(ValueError):
        intervalo_wilson(-1, 10)


def test_sobrepoe_e_simetrico_e_detecta_os_dois_sentidos() -> None:
    a = intervalo_wilson(6, 20)  # 14,5475 .. 51,8977
    b = intervalo_wilson(80, 100)  # 71,12 .. 86,66 — não sobrepõe a
    c = intervalo_wilson(15, 20)  # 53,13 .. 88,81 — sobrepõe a? não; sobrepõe b? sim

    assert sobrepoe(a, b) is False
    assert sobrepoe(b, a) is False
    assert sobrepoe(b, c) is True
    assert sobrepoe(c, b) is True


def test_sobrepoe_com_valores_do_teste_de_padroes() -> None:
    subgrupo = intervalo_wilson(14, 20)
    base = intervalo_wilson(75, 100)
    assert sobrepoe(subgrupo, base) is True
