# O que é: testes do passo 7 da V2 — contrato Pydantic do `DnaConcurso` (skill dna-do-concurso),
# `montar_dna_por_regras` e `verificar_dna`. Quando ler: ao mudar o contrato ou as regras.
import json
import re
from datetime import date
from pathlib import Path

import pytest

from aprovaos.dominio.dna import DnaConcurso, PesoTopico, montar_dna_por_regras, verificar_dna
from aprovaos.dominio.edital import MateriaExtraida, extrair_conteudo_programatico, sem_acento

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_MD = RAIZ / "docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md"

# Copiado literalmente de `.claude/skills/dna-do-concurso/SKILL.md` (seção "A saída é este JSON").
JSON_DA_SKILL = """{
  "concurso": {"orgao": "", "cargo": "", "banca": "", "edital": "", "data_prova": "desconhecido", "fonte": "edital §1.1, §1.2, §6.5"},
  "regra_correcao": {"tipo_item": "multipla_escolha", "alternativas": 5, "anula_por_erro": false, "minimo_por_materia": "nota zero elimina", "minimo_global": "50 % dos pontos", "fonte": "edital §6.1, §6.3"},
  "etapas": [{"nome": "objetiva", "pontos": 80, "fonte": "edital §6.2"}, {"nome": "discursiva", "pontos": 20, "quem_faz": "60 primeiros", "fonte": "edital §6.4"}],
  "pesos": {"materia": {"lingua-portuguesa": {"questoes": 10, "peso_questao": 1.0, "pontos": 10, "pct_pontos": 12.5, "fonte": "edital §6.2"}},
            "topico": {"dir-adm-04-licitacoes": {"pct_pontos": "desconhecido", "metodo": "uniforme_no_edital", "pct_uniforme": 10.7}}},
  "topicos_edital": [{"slug": "dir-adm-04-licitacoes", "materia": "direito-administrativo", "texto_original": "4. Licitações e contratos — Lei nº 14.133/2021.", "fonte": "edital Anexo I"}],
  "incidencia": {"por_topico": "desconhecido", "provas_analisadas": 0, "fonte": "nenhuma prova da banca na base"},
  "estilo": {"tipo_item": "multipla_escolha", "alternativas": 5, "caracteristicas": "desconhecido", "fonte": "edital §6.1; sem provas"},
  "pegadinhas": [],
  "corte": {"lo": "desconhecido", "hi": "desconhecido", "fonte": "sem provas/resultados anteriores"},
  "lacunas": ["incidencia por tópico", "estilo da banca", "corte histórico", "pegadinhas"],
  "fontes": ["edital 01/2026 (arquivo subido)"],
  "versao": 1
}"""  # noqa: E501

ORDEM_DAS_CHAVES = [
    "concurso",
    "regra_correcao",
    "etapas",
    "pesos",
    "topicos_edital",
    "incidencia",
    "estilo",
    "pegadinhas",
    "corte",
    "lacunas",
    "fontes",
    "versao",
]


def _normalizar(texto: str) -> str:
    return sem_acento(texto).lower()


def _lacunas_contem(dna: DnaConcurso, termo: str) -> bool:
    return any(termo in _normalizar(lacuna) for lacuna in dna.lacunas)


@pytest.fixture
def texto_md() -> str:
    return FIXTURE_MD.read_text(encoding="utf-8")


@pytest.fixture
def materias(texto_md: str) -> list[MateriaExtraida]:
    return extrair_conteudo_programatico(texto_md)


@pytest.fixture
def dna_regras(texto_md: str, materias: list[MateriaExtraida]) -> DnaConcurso:
    return montar_dna_por_regras(texto_md, materias)


def test_dna_valida_o_exemplo_da_skill() -> None:
    dna = DnaConcurso.model_validate_json(JSON_DA_SKILL)
    despejo = dna.model_dump(mode="json")
    assert list(despejo) == ORDEM_DAS_CHAVES
    assert despejo["pesos"]["topico"]["dir-adm-04-licitacoes"]["pct_uniforme"] == 10.7
    assert despejo["concurso"]["data_prova"] == "desconhecido"
    assert list(despejo["regra_correcao"]) == [
        "tipo_item",
        "alternativas",
        "anula_por_erro",
        "minimo_por_materia",
        "minimo_global",
        "fonte",
    ]
    # Ida e volta por JSON preserva o conteúdo (é o que vai para `dna_concurso.conteudo`).
    assert DnaConcurso.model_validate(json.loads(json.dumps(despejo))) == dna


def test_montar_dna_por_regras_fixture(dna_regras: DnaConcurso) -> None:
    dna = dna_regras
    assert list(dna.pesos.materia) == [
        "lingua-portuguesa",
        "raciocinio-logico",
        "legislacao-municipal",
        "conhecimentos-especificos",
    ]
    assert [m.pct_pontos for m in dna.pesos.materia.values()] == [12.5, 6.25, 6.25, 75.0]
    assert [m.pontos for m in dna.pesos.materia.values()] == [10, 5, 5, 60]
    assert [m.questoes for m in dna.pesos.materia.values()] == [10, 5, 5, 30]
    assert all(m.fonte == "edital §6.2" for m in dna.pesos.materia.values())
    assert dna.etapas[0].pontos == 80
    assert dna.etapas[1].quem_faz == "60 primeiros"
    # `pytest.approx` não passa pela validação do Pydantic: compara-se campo a campo.
    licitacoes = dna.pesos.topico["dir-adm-04-licitacoes-contratos"]
    assert isinstance(licitacoes, PesoTopico)
    assert licitacoes.pct_pontos == "desconhecido"
    assert licitacoes.metodo == "uniforme_no_edital"
    assert licitacoes.pct_uniforme == pytest.approx(75 / 22, abs=0.01)
    assert dna.pesos.topico["lin-por-01-compreensao-interpretacao"].pct_uniforme == pytest.approx(
        12.5 / 7, abs=0.01
    )
    assert len(dna.topicos_edital) == 36
    assert len(dna.pesos.topico) == 36
    assert dna.topicos_edital[0].fonte == "edital Anexo I"
    assert dna.topicos_edital[0].materia == "lingua-portuguesa"
    assert dna.regra_correcao.minimo_global == "50 % do total de pontos (40 de 80)"
    assert dna.regra_correcao.minimo_por_materia == "nota zero elimina"
    assert dna.concurso.orgao == "CÂMARA MUNICIPAL DE CASCAVEL — ESTADO DO PARANÁ"
    assert dna.concurso.cargo == "ASSESSOR DE GABINETE"
    assert dna.concurso.banca == "FUNDAÇÃO DE APOIO À UNIOESTE"
    assert dna.concurso.edital == "01/2026"
    assert dna.concurso.data_prova == date(2026, 11, 15)
    assert dna.concurso.fonte == "edital §1.1, §1.2, §6.5"
    assert dna.incidencia.provas_analisadas == 0
    assert dna.incidencia.por_topico == "desconhecido"
    assert dna.estilo.tipo_item == "multipla_escolha"
    assert dna.estilo.alternativas == 5
    assert dna.estilo.caracteristicas == "desconhecido"
    assert dna.estilo.fonte == "edital §6.1, §6.3; sem provas"
    assert dna.corte.lo == "desconhecido"
    assert dna.pegadinhas == []
    for termo in ("incidencia", "estilo", "corte", "pegadinhas"):
        assert _lacunas_contem(dna, termo), termo
    # "estilo da banca" contém "banca": a lacuna específica de banca é a palavra sozinha.
    assert "banca" not in dna.lacunas
    assert not _lacunas_contem(dna, "distribuicao")
    assert dna.fontes == ["edital 01/2026 (arquivo subido)"]
    assert dna.versao == 1


def test_soma_dos_pct_uniforme_e_100(dna_regras: DnaConcurso) -> None:
    pesos = dna_regras.pesos.topico.values()
    soma = sum(t.pct_uniforme for t in pesos if isinstance(t.pct_uniforme, float))
    assert soma == pytest.approx(100)


def test_montar_dna_sem_distribuicao(texto_md: str, materias: list[MateriaExtraida]) -> None:
    sem_62 = re.sub(r"^6\.2 .*\n", "", texto_md, flags=re.MULTILINE)
    assert "6.2" not in sem_62
    dna = montar_dna_por_regras(sem_62, materias)
    assert len(dna.pesos.materia) == 4
    for peso in dna.pesos.materia.values():
        assert peso.questoes == "desconhecido"
        assert peso.peso_questao == 1.0
        assert peso.pontos == "desconhecido"
        assert peso.pct_pontos == "desconhecido"
        assert peso.fonte == "edital omisso — assumido 1,0"
    assert all(t.pct_uniforme == "desconhecido" for t in dna.pesos.topico.values())
    assert dna.etapas[0].pontos == "desconhecido"
    assert dna.regra_correcao.minimo_global == "50 % do total de pontos"
    assert _lacunas_contem(dna, "distribuicao")
    assert verificar_dna(dna, materias) == []


def test_montar_dna_com_materia_fora_da_distribuicao(
    texto_md: str, materias: list[MateriaExtraida]
) -> None:
    com_informatica = texto_md.replace(
        "peso 1,0; Raciocínio Lógico",
        "peso 1,0; Informática — 5 questões, peso 1,0; Raciocínio Lógico",
    )
    dna = montar_dna_por_regras(com_informatica, materias)
    assert "informatica" in dna.pesos.materia
    assert dna.pesos.materia["informatica"].pct_pontos == pytest.approx(5 / 85 * 100)
    assert _lacunas_contem(dna, "informatica")
    assert verificar_dna(dna, materias) == []


def test_montar_dna_com_banca_e_data_desconhecidas(materias: list[MateriaExtraida]) -> None:
    texto = (
        "PREFEITURA DE EXEMPLO\n"
        "ANEXO I — CONTEÚDO PROGRAMÁTICO\n"
        "LÍNGUA PORTUGUESA: 1. Compreensão e interpretação de textos.\n"
    )
    materias_min = extrair_conteudo_programatico(texto)
    dna = montar_dna_por_regras(texto, materias_min)
    assert dna.concurso.banca == "desconhecido"
    assert dna.concurso.data_prova == "desconhecido"
    assert dna.regra_correcao.tipo_item == "desconhecido"
    assert dna.fontes == ["edital (arquivo subido)"]
    for termo in ("banca", "data", "correcao"):
        assert _lacunas_contem(dna, termo), termo
    assert verificar_dna(dna, materias_min) == []


def test_verificar_dna_aprova_o_das_regras(
    dna_regras: DnaConcurso, materias: list[MateriaExtraida]
) -> None:
    assert verificar_dna(dna_regras, materias) == []


def test_verificar_dna_reprova(dna_regras: DnaConcurso, materias: list[MateriaExtraida]) -> None:
    dna = dna_regras

    pct_errado = dna.model_copy(deep=True)
    pct_errado.pesos.materia["lingua-portuguesa"].pct_pontos = 20
    assert any("soma" in p for p in verificar_dna(pct_errado, materias))

    sem_fonte = dna.model_copy(deep=True)
    sem_fonte.pesos.materia["lingua-portuguesa"].fonte = ""
    assert any("sem fonte" in p for p in verificar_dna(sem_fonte, materias))

    fonte_inventada = dna.model_copy(deep=True)
    fonte_inventada.corte.fonte = "estimativa do modelo"
    assert any("fonte" in p for p in verificar_dna(fonte_inventada, materias))

    sem_lacunas = dna.model_copy(deep=True)
    sem_lacunas.lacunas = []
    assert any("lacuna" in p for p in verificar_dna(sem_lacunas, materias))

    incompleto = dna.model_copy(deep=True)
    incompleto.topicos_edital = incompleto.topicos_edital[1:]
    problemas = verificar_dna(incompleto, materias)
    assert any("cobertura" in p and "35 de 36" in p for p in problemas)

    slug_trocado = dna.model_copy(deep=True)
    slug_trocado.topicos_edital[0].slug = "lin-por-01-inventado"
    assert any("cobertura" in p for p in verificar_dna(slug_trocado, materias))
