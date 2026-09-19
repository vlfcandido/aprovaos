# O que é: testes de `dominio/rotina.py` — validação de `DadosRotina` (F2.2). Sem banco.
# Quando ler: ao mexer no formulário de rotina.
import pytest
from pydantic import ValidationError

from aprovaos.dominio.rotina import DIAS_SEMANA, DadosRotina

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
