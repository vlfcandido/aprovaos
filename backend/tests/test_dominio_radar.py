# O que é: testes dos passos 1 e 2 do plano `docs/fatias/1b-radar-e-conta.md` — leitura pura do
# catálogo da Cebraspe e o casamento com o perfil da aluna. Quando ler: ao mexer em
# `aprovaos/dominio/radar.py`.
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from aprovaos.dominio.radar import (
    Casamento,
    ConcursoDoRadar,
    PreferenciaRadar,
    casar_com_perfil,
    extrair_uf,
    ler_catalogo,
    ler_periodo_inscricao,
)

RAIZ_FIXTURES = (
    Path(__file__).resolve().parents[2] / "knowledge" / "fixtures" / "fontes" / "cebraspe"
)


def _carregar(nome: str) -> Any:
    return json.loads((RAIZ_FIXTURES / nome).read_text(encoding="utf-8"))


@pytest.fixture
def catalogo() -> Any:
    return _carregar("catalogo-todas-as-fases-2026-09-19.json")


def test_le_os_quatro_grupos_com_as_contagens_medidas(catalogo: Any) -> None:
    """1 novo, 8 inscrições abertas, 63 em andamento, 424 encerrados (medido em 19/09/2026)."""
    concursos = ler_catalogo(catalogo)

    por_fase: dict[str, int] = {}
    for c in concursos:
        por_fase[c.fase] = por_fase.get(c.fase, 0) + 1

    assert por_fase == {
        "novos": 1,
        "inscricoes_abertas": 8,
        "em_andamento": 63,
        "encerrado": 424,
    }


def test_fase_vem_do_corpo_nunca_inventa_grupo_desconhecido() -> None:
    """Um `faseEvento` fora dos quatro conhecidos falha alto — nunca é descartado em silêncio."""
    payload = [{"faseEvento": "Cancelados", "ordem": 9, "eventos": []}]
    with pytest.raises(ValueError, match="Cancelados"):
        ler_catalogo(payload)


def test_catalogo_que_nao_e_lista_falha_alto() -> None:
    with pytest.raises(ValueError):
        ler_catalogo({"eventos": []})


def test_agepar_pr_tem_uf_confirmada(catalogo: Any) -> None:
    concursos = {c.evento_url: c for c in ler_catalogo(catalogo)}
    assert concursos["AGEPAR_PR_26"].uf == "PR"


def test_agu_estagiario_fica_sem_uf(catalogo: Any) -> None:
    """ "AGU 26 ESTAGIARIO" não tem token de duas letras que seja UF — `uf=None`, nunca chutado."""
    concursos = {c.evento_url: c for c in ler_catalogo(catalogo)}
    assert concursos["AGU_26_ESTAGIARIO"].uf is None


def test_camara_municipal_ponta_pora_tem_uf_ms(catalogo: Any) -> None:
    concursos = {c.evento_url: c for c in ler_catalogo(catalogo)}
    assert concursos["CAMARA_MUNICIPAL_PONTAPORA_MS_26"].uf == "MS"


def test_extrair_uf_exige_confirmacao_nos_dois_lados() -> None:
    assert extrair_uf("AGEPAR PR 26", "AGEPAR_PR_26") == "PR"
    # "SP" aparece no nome, mas no eventoURL ela está colada a outro token (não isolada por "_")
    # -> não confirma, `uf=None` (Ruling 39: nunca uma UF chutada).
    assert extrair_uf("ORGAO SP TESTE 26", "ORGAO_SPTESTE_26") is None


def test_salario_zero_ou_ausente_vira_none_com_lacuna(catalogo: Any) -> None:
    concursos = {c.evento_url: c for c in ler_catalogo(catalogo)}
    tj_ce = concursos["TJ_CE_25_NOTARIOS"]
    assert tj_ce.salario_max_brl is None
    assert "salário não informado" in tj_ce.lacunas

    agepar = concursos["AGEPAR_PR_26"]
    assert agepar.salario_max_brl == Decimal("9975")


def test_data_da_prova_e_sempre_lacuna_declarada(catalogo: Any) -> None:
    concursos = ler_catalogo(catalogo)
    assert all("data da prova não publicada na API" in c.lacunas for c in concursos)


def test_ler_periodo_inscricao_no_formato_medido() -> None:
    texto = "De 23/07/2026 até 21/08/2026 às 18:00, horário oficial de Brasília/DF"
    assert ler_periodo_inscricao(texto) == (date(2026, 7, 23), date(2026, 8, 21))


def test_ler_periodo_inscricao_texto_none() -> None:
    assert ler_periodo_inscricao(None) == (None, None)


def test_ler_periodo_inscricao_formato_desconhecido_nunca_adivinha() -> None:
    assert ler_periodo_inscricao("de 23 a 21 de agosto") == (None, None)


def _concurso(**sobrescritas: Any) -> ConcursoDoRadar:
    base: dict[str, Any] = {
        "evento_url": "AGEPAR_PR_26",
        "nome": "AGEPAR PR 26",
        "ano": 2026,
        "fase": "em_andamento",
        "uf": "PR",
        "vagas": 23,
        "salario_max_brl": Decimal("9975"),
        "periodo_inscricao_texto": None,
        "inscricao_inicio": None,
        "inscricao_fim": None,
        "lacunas": [],
    }
    base.update(sobrescritas)
    return ConcursoDoRadar.model_validate(base)


def test_sem_preferencia_nenhuma_nunca_combina() -> None:
    concurso = _concurso()
    preferencia = PreferenciaRadar(ufs=[], salario_minimo_brl=None, area="qualquer")

    resultado = casar_com_perfil(concurso, preferencia, cargos=[])

    assert resultado == Casamento(combina=False, motivos=[], contra=[])


def test_combina_por_uf_e_salario() -> None:
    concurso = _concurso(uf="PR", salario_max_brl=Decimal("9975"))
    preferencia = PreferenciaRadar(ufs=["PR"], salario_minimo_brl=Decimal("5000"), area="qualquer")

    resultado = casar_com_perfil(concurso, preferencia, cargos=[])

    assert resultado.combina is True
    assert "PR" in resultado.motivos
    assert "salário acima do seu mínimo" in resultado.motivos
    assert resultado.contra == []


def test_nao_combina_mostra_o_contra() -> None:
    concurso = _concurso(uf="SP", salario_max_brl=Decimal("2000"))
    preferencia = PreferenciaRadar(ufs=["PR"], salario_minimo_brl=Decimal("5000"), area="qualquer")

    resultado = casar_com_perfil(concurso, preferencia, cargos=[])

    assert resultado.combina is False
    assert "UF fora do seu interesse (SP)" in resultado.contra
    assert "salário abaixo do seu mínimo" in resultado.contra


def test_area_direito_reusa_o_lexico_de_cargo_de_direito() -> None:
    concurso = _concurso()
    preferencia = PreferenciaRadar(ufs=[], salario_minimo_brl=None, area="direito")
    cargos = ["CARGO 3: ESPECIALISTA EM REGULAÇÃO – ESPECIALIDADE: DIREITO"]

    resultado = casar_com_perfil(concurso, preferencia, cargos=cargos)

    assert resultado.combina is True
    assert "cargo de Direito" in resultado.motivos


def test_area_direito_sem_cargo_de_direito_no_detalhe() -> None:
    concurso = _concurso()
    preferencia = PreferenciaRadar(ufs=[], salario_minimo_brl=None, area="direito")
    cargos = ["CARGO 1: ESPECIALISTA EM REGULAÇÃO – ESPECIALIDADE: CONTABILIDADE"]

    resultado = casar_com_perfil(concurso, preferencia, cargos=cargos)

    assert resultado.combina is False
    assert "nenhum cargo de Direito identificado" in resultado.contra


def test_area_direito_sem_detalhe_nao_acusa_contra() -> None:
    """Sem cargos (detalhe não consultado nesta rodada), não é honesto dizer "não é Direito"."""
    concurso = _concurso()
    preferencia = PreferenciaRadar(ufs=[], salario_minimo_brl=None, area="direito")

    resultado = casar_com_perfil(concurso, preferencia, cargos=[])

    assert resultado.contra == []
