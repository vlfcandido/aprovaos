# O que é: testes de `dominio/rotina.py` — validação de `DadosRotina` (F2.2). Sem banco.
# Quando ler: ao mexer no formulário de rotina.
import pytest
from pydantic import ValidationError

from aprovaos.dominio.rotina import (
    DIAS_FIM_DE_SEMANA,
    DIAS_SEMANA,
    DIAS_UTEIS,
    PRESET_MANUAL,
    DadosRotina,
    horas_a_partir_das_escolhas,
    preset_das_horas,
    total_semanal,
)

HORAS_VALIDAS = {dia: 2.0 for dia in DIAS_SEMANA}


def test_dados_rotina_aceita_entrada_valida() -> None:
    dados = DadosRotina(
        horas_por_dia_semana=HORAS_VALIDAS,
        horario_preferido="manha",
        energia_tipica="media",
        data_alvo=None,
        concurso_principal_id=None,
    )
    assert dados.horas_por_dia_semana["seg"] == 2.0


def test_dados_rotina_exige_os_sete_dias() -> None:
    incompleto = {dia: 2.0 for dia in DIAS_SEMANA if dia != "dom"}
    with pytest.raises(ValidationError):
        DadosRotina(
            horas_por_dia_semana=incompleto,
            horario_preferido="manha",
            energia_tipica="media",
            data_alvo=None,
            concurso_principal_id=None,
        )


@pytest.mark.parametrize("horas", [-1.0, 25.0])
def test_dados_rotina_rejeita_horas_fora_da_faixa(horas: float) -> None:
    invalido = dict(HORAS_VALIDAS)
    invalido["seg"] = horas
    with pytest.raises(ValidationError):
        DadosRotina(
            horas_por_dia_semana=invalido,
            horario_preferido="manha",
            energia_tipica="media",
            data_alvo=None,
            concurso_principal_id=None,
        )


def test_dados_rotina_rejeita_energia_fora_do_enum() -> None:
    with pytest.raises(ValidationError):
        DadosRotina(
            horas_por_dia_semana=HORAS_VALIDAS,
            horario_preferido="manha",
            energia_tipica="excelente",
            data_alvo=None,
            concurso_principal_id=None,
        )


def test_dados_rotina_rejeita_horario_fora_das_opcoes() -> None:
    with pytest.raises(ValidationError):
        DadosRotina(
            horas_por_dia_semana=HORAS_VALIDAS,
            horario_preferido="madrugada",
            energia_tipica="media",
            data_alvo=None,
            concurso_principal_id=None,
        )


# ---- atalhos de tempo (23/09/2026): a tela de rotina deixou de ser sete campos para digitar ----
# "tela de sua rotina tá péssima pra ficar digitando os dados ali" (dono). O caminho principal
# passou a ser um atalho por grupo de dias; o campo dia a dia virou a exceção, atrás de um
# `<details>`. Estas funções são a regra de precedência entre os dois, e ela precisa valer
# **sem JS** — é o servidor que decide, não o navegador.


def test_atalho_aplica_o_mesmo_numero_de_horas_a_todos_os_dias_do_grupo() -> None:
    horas = horas_a_partir_das_escolhas("2", "4", dict.fromkeys(DIAS_SEMANA, 0.0))

    assert [horas[dia] for dia in DIAS_UTEIS] == [2.0] * 5
    assert [horas[dia] for dia in DIAS_FIM_DE_SEMANA] == [4.0, 4.0]


def test_atalho_de_nao_estudar_zera_o_grupo() -> None:
    """ "Não estudo" é uma resposta legítima: descansar é recomendação válida (visão §4)."""
    horas = horas_a_partir_das_escolhas("2", "0", dict.fromkeys(DIAS_SEMANA, 3.0))

    assert horas["sex"] == 2.0
    assert horas["sab"] == 0.0
    assert horas["dom"] == 0.0


def test_dia_a_dia_vence_quando_e_a_escolha_do_grupo() -> None:
    """É a escape hatch de quem quer precisão — e ela precisa vencer o atalho, nunca o contrário."""
    digitadas = dict.fromkeys(DIAS_SEMANA, 0.0) | {"seg": 1.5, "ter": 2.5, "sab": 6.0}

    horas = horas_a_partir_das_escolhas(PRESET_MANUAL, "3", digitadas)

    assert horas["seg"] == 1.5
    assert horas["ter"] == 2.5
    assert horas["sab"] == 3.0


def test_sem_atalho_nenhum_valem_os_campos_digitados() -> None:
    """O contrato antigo do formulário continua de pé: quem posta só `hora_*` grava `hora_*`."""
    digitadas = dict.fromkeys(DIAS_SEMANA, 0.0) | {"seg": 2.0, "sab": 4.0}

    horas = horas_a_partir_das_escolhas("", "", digitadas)

    assert horas["seg"] == 2.0
    assert horas["sab"] == 4.0


def test_atalho_fora_da_lista_nao_e_aceito_e_cai_no_digitado() -> None:
    """Valor forjado no formulário não vira hora de estudo inventada."""
    digitadas = dict.fromkeys(DIAS_SEMANA, 1.0)

    horas = horas_a_partir_das_escolhas("99", "abacaxi", digitadas)

    assert set(horas.values()) == {1.0}


def test_horas_a_partir_das_escolhas_devolve_sempre_os_sete_dias() -> None:
    """`DadosRotina` exige os sete; dia ausente no formulário vale zero, não some."""
    horas = horas_a_partir_das_escolhas("", "", {"seg": 2.0})

    assert set(horas) == set(DIAS_SEMANA)
    assert horas["dom"] == 0.0


@pytest.mark.parametrize(
    ("valores", "esperado"),
    [(0.0, "0"), (1.0, "1"), (2.0, "2"), (3.0, "3"), (4.0, "4")],
)
def test_atalho_reconhecido_de_volta_a_partir_das_horas_salvas(
    valores: float, esperado: str
) -> None:
    """A tela reabre com o atalho que a pessoa escolheu marcado, não com tudo em branco."""
    horas = dict.fromkeys(DIAS_SEMANA, valores)

    assert preset_das_horas(horas, DIAS_UTEIS) == esperado


def test_horas_desiguais_no_grupo_voltam_como_dia_a_dia() -> None:
    """Quem ajustou fino reabre a tela no modo fino, com o `<details>` já aberto."""
    horas = dict.fromkeys(DIAS_SEMANA, 2.0) | {"qua": 1.0}

    assert preset_das_horas(horas, DIAS_UTEIS) == PRESET_MANUAL


def test_horas_iguais_mas_fora_da_lista_voltam_como_dia_a_dia() -> None:
    """2,5 h todo dia é uma rotina real e não tem atalho: o modo fino é a resposta honesta."""
    horas = dict.fromkeys(DIAS_SEMANA, 2.5)

    assert preset_das_horas(horas, DIAS_FIM_DE_SEMANA) == PRESET_MANUAL


def test_total_da_semana_soma_os_sete_dias() -> None:
    """O número que a tela mostra de volta ("isso dá N h por semana") sai daqui, não do JS."""
    assert total_semanal(dict.fromkeys(DIAS_SEMANA, 2.0)) == 14.0
    assert total_semanal({"seg": 1.5, "sab": 3.0}) == 4.5
