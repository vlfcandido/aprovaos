# O que é: testes de `dominio/previsao.py` — a previsão de nota v0 (RF-18, fatia 10 §5 do plano
# `docs/fatias/10-painel.md`). Sem banco: `DesempenhoMateria` construído à mão com proporções já
# calculadas por `intervalo_wilson`. Quando ler: ao mudar o critério de confiança ou como o corte
# histórico entra na comparação.
import pytest

from aprovaos.dominio.estatistica import intervalo_wilson
from aprovaos.dominio.previsao import DesempenhoMateria, prever_nota


def test_materia_sem_dado_nao_vira_zero_nem_entra_na_media() -> None:
    com_dado = DesempenhoMateria(
        materia="Direito Administrativo", proporcao=intervalo_wilson(80, 100), peso_questoes=5
    )
    sem_dado = DesempenhoMateria(materia="Direito Constitucional", proporcao=None, peso_questoes=5)

    previsao = prever_nota([com_dado, sem_dado])

    assert previsao.nota_pct == pytest.approx(80.0)
    assert previsao.materias_sem_dado == ["Direito Constitucional"]


def test_peso_maior_puxa_a_nota_para_perto_de_si() -> None:
    peso_alto = DesempenhoMateria(
        materia="Direito Administrativo", proporcao=intervalo_wilson(90, 100), peso_questoes=18
    )
    peso_baixo = DesempenhoMateria(
        materia="Português", proporcao=intervalo_wilson(30, 100), peso_questoes=2
    )

    previsao = prever_nota([peso_alto, peso_baixo])

    # média simples seria 60; ponderada por peso deve ficar bem mais perto de 90.
    assert previsao.nota_pct > 75.0


def test_banda_estreita_com_muito_dado_da_confianca_alta() -> None:
    materia = DesempenhoMateria(
        materia="Direito Administrativo", proporcao=intervalo_wilson(900, 1000), peso_questoes=10
    )
    previsao = prever_nota([materia])
    assert previsao.nota_superior_pct - previsao.nota_inferior_pct <= 10
    assert previsao.confianca == "alta"


def test_pouca_cobertura_da_confianca_baixa() -> None:
    com_dado = DesempenhoMateria(
        materia="Direito Administrativo", proporcao=intervalo_wilson(3, 5), peso_questoes=2
    )
    sem_dado_1 = DesempenhoMateria(materia="Português", proporcao=None, peso_questoes=9)
    sem_dado_2 = DesempenhoMateria(materia="Raciocínio Lógico", proporcao=None, peso_questoes=9)

    previsao = prever_nota([com_dado, sem_dado_1, sem_dado_2])
    assert previsao.confianca == "baixa"


def test_porque_concorda_o_numero_de_questoes_da_materia_de_maior_peso() -> None:
    """Defeito reproduzido no navegador (fatia 14): "pesa mais (1 questões)" — sem concordância.
    Com peso 1, o texto tem que dizer "1 questão"; com mais de uma, "N questões"."""
    materia_peso_um = DesempenhoMateria(
        materia="Redação", proporcao=intervalo_wilson(1, 1), peso_questoes=1
    )
    previsao = prever_nota([materia_peso_um])
    assert "1 questão)" in previsao.porque
    assert "1 questões)" not in previsao.porque

    materia_peso_dois = DesempenhoMateria(
        materia="Direito Administrativo", proporcao=intervalo_wilson(8, 10), peso_questoes=2
    )
    previsao_plural = prever_nota([materia_peso_dois])
    assert "2 questões)" in previsao_plural.porque


def test_probabilidade_lacuna_sem_codigo_interno_de_pendencia() -> None:
    """Defeito reproduzido no navegador (fatia 14): `(P-17/P-39)` vazava na tela da aluna."""
    materia = DesempenhoMateria(
        materia="Direito Administrativo", proporcao=intervalo_wilson(80, 100), peso_questoes=10
    )
    previsao = prever_nota([materia], corte_historico_pct=None)
    assert previsao.probabilidade_lacuna is not None
    assert "P-" not in previsao.probabilidade_lacuna


def test_sem_corte_historico_e_lacuna_declarada_sem_probabilidade() -> None:
    materia = DesempenhoMateria(
        materia="Direito Administrativo", proporcao=intervalo_wilson(80, 100), peso_questoes=10
    )
    previsao = prever_nota([materia], corte_historico_pct=None)
    assert previsao.corte_historico_pct is None
    assert previsao.probabilidade_lacuna is not None
    assert "corte histórico" in previsao.probabilidade_lacuna


def test_com_corte_a_comparacao_sai_pela_banda_nao_pelo_ponto() -> None:
    # nota ~66,7 (2 de 3), banda de Wilson bem larga (20,8 a 93,9) por causa do n pequeno.
    # pelo ponto, corte=80 pareceria "abaixo" (66,7 < 80); mas 80 está dentro da banda
    # (20,8–93,9), então a leitura honesta é "em cima do corte", não "abaixo".
    materia = DesempenhoMateria(
        materia="Direito Administrativo", proporcao=intervalo_wilson(2, 3), peso_questoes=10
    )
    previsao = prever_nota([materia], corte_historico_pct=80.0)

    assert previsao.probabilidade_lacuna is None
    assert previsao.nota_pct < 80.0
    assert "em cima do corte" in previsao.porque
