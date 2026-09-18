# O que é: testes dos passos 5 e 6 da V2 — parser do conteúdo programático, slugs e fatos do
# edital por regex. Quando ler: ao mudar `aprovaos/dominio/edital.py` ou a fixture do edital.
import re
from datetime import date
from pathlib import Path

import pytest

from aprovaos.dominio.edital import (
    Etapa,
    extrair_conteudo_programatico,
    extrair_fatos,
    fonte_conteudo_programatico,
    prefixo_materia,
    slug_materia,
    slug_topico,
)
from aprovaos.dominio.erros import ConteudoProgramaticoNaoEncontrado

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_MD = RAIZ / "docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md"
FIXTURE_PDF = RAIZ / "knowledge/fixtures/editais/edital-assessor-gabinete.pdf"

MATERIAS_ESPERADAS = [
    "LÍNGUA PORTUGUESA",
    "RACIOCÍNIO LÓGICO",
    "LEGISLAÇÃO MUNICIPAL",
    "DIREITO CONSTITUCIONAL",
    "DIREITO ADMINISTRATIVO",
    "DIREITO CIVIL",
    "DIREITO PROCESSUAL CIVIL",
]
CONTAGENS_ESPERADAS = [7, 4, 3, 6, 7, 4, 5]
REGEX_SLUG = re.compile(r"^[a-z]{1,3}(-[a-z]{1,3})*-\d{2}-[a-z0-9]+(-[a-z0-9]+)?$")


@pytest.fixture
def texto_md() -> str:
    return FIXTURE_MD.read_text(encoding="utf-8")


def _conferir_fixture(texto: str) -> None:
    materias = extrair_conteudo_programatico(texto)
    assert [m.nome for m in materias] == MATERIAS_ESPERADAS
    assert [len(m.topicos) for m in materias] == CONTAGENS_ESPERADAS
    assert sum(len(m.topicos) for m in materias) == 36
    assert [m.grupo for m in materias] == [None] * 3 + ["CONHECIMENTOS ESPECÍFICOS"] * 4
    direito_adm = materias[4]
    assert direito_adm.slug == "direito-administrativo"
    item4 = direito_adm.topicos[3]
    assert item4.numero == 4
    assert item4.texto_original == "4. Licitações e contratos — Lei nº 14.133/2021."
    assert item4.slug == "dir-adm-04-licitacoes-contratos"
    for materia in materias:
        assert [t.numero for t in materia.topicos] == list(range(1, len(materia.topicos) + 1))
        for topico in materia.topicos:
            assert REGEX_SLUG.match(topico.slug), topico.slug
            assert "\n" not in topico.texto_original


def test_parser_fixture_md_36_topicos(texto_md: str) -> None:
    _conferir_fixture(texto_md)


def test_parser_fixture_pdf_36_topicos() -> None:
    pdf = pytest.importorskip("aprovaos.dominio.pdf")
    if not FIXTURE_PDF.exists():
        pytest.skip("fixture PDF ainda não gerada (passo 3 da V2)")
    _conferir_fixture(pdf.extrair_texto(FIXTURE_PDF.read_bytes()))


def test_item_quebrado_em_duas_linhas() -> None:
    texto = (
        "CONTEÚDO PROGRAMÁTICO\n"
        "DIREITO CIVIL: 1. Lei de Introdução às\n"
        "Normas do Direito Brasileiro. 2. Pessoas\n"
        "naturais e jurídicas."
    )
    materias = extrair_conteudo_programatico(texto)
    assert len(materias) == 1
    assert [t.texto_original for t in materias[0].topicos] == [
        "1. Lei de Introdução às Normas do Direito Brasileiro.",
        "2. Pessoas naturais e jurídicas.",
    ]


def test_item_com_numero_no_fim_da_linha_e_palavra_partida() -> None:
    # Saída real do pypdfium2 para um PDF do reportlab: o número fica no fim da linha e uma
    # palavra hifenizada é partida entre linhas.
    texto = (
        "ANEXO I — CONTEÚDO PROGRAMÁTICO\n"
        "DIREITO CONSTITUCIONAL: 1. Constituição: conceito, poder constitu-\n"
        "inte. 2.\n"
        "Direitos e garantias fundamentais. 3. Controle de\n"
        "constitucionalidade.\n"
        "ANEXO II — CRONOGRAMA\n"
        "1. Inscrições. 2. Provas."
    )
    materias = extrair_conteudo_programatico(texto)
    assert len(materias) == 1
    assert [t.texto_original for t in materias[0].topicos] == [
        "1. Constituição: conceito, poder constituinte.",
        "2. Direitos e garantias fundamentais.",
        "3. Controle de constitucionalidade.",
    ]


def test_materia_sem_dois_pontos() -> None:
    texto = "CONTEÚDO PROGRAMÁTICO\nDIREITO TRIBUTÁRIO 1. Tributos. 2. Competência tributária."
    materias = extrair_conteudo_programatico(texto)
    assert len(materias) == 1
    assert materias[0].nome == "DIREITO TRIBUTÁRIO"
    assert [t.texto_original for t in materias[0].topicos] == [
        "1. Tributos.",
        "2. Competência tributária.",
    ]


def test_sem_conteudo_programatico() -> None:
    with pytest.raises(ConteudoProgramaticoNaoEncontrado) as erro:
        extrair_conteudo_programatico("EDITAL 01/2026\n1. Das disposições.")
    assert "conteúdo programático" in str(erro.value)


def test_slugs() -> None:
    assert slug_materia("LÍNGUA PORTUGUESA") == "lingua-portuguesa"
    assert slug_materia("CONHECIMENTOS ESPECÍFICOS") == "conhecimentos-especificos"
    assert prefixo_materia("DIREITO ADMINISTRATIVO") == "dir-adm"
    assert prefixo_materia("LÍNGUA PORTUGUESA") == "lin-por"
    assert prefixo_materia("DIREITO PROCESSUAL CIVIL") == "dir-pro-civ"
    assert (
        slug_topico("DIREITO ADMINISTRATIVO", 4, "4. Licitações e contratos — Lei nº 14.133/2021.")
        == "dir-adm-04-licitacoes-contratos"
    )
    assert (
        slug_topico("LÍNGUA PORTUGUESA", 1, "1. Compreensão e interpretação de textos.")
        == "lin-por-01-compreensao-interpretacao"
    )
    assert slug_topico("DIREITO CIVIL", 1, "1. Lei de Introdução às Normas.") == (
        "dir-civ-01-lei-introducao"
    )
    for slug in (
        slug_topico("RACIOCÍNIO LÓGICO", 2, "2. Tabelas-verdade."),
        slug_topico("DIREITO ADMINISTRATIVO", 1, "1. Princípios da Administração Pública."),
    ):
        assert REGEX_SLUG.match(slug), slug


# ---- Passo 6: fatos do edital por regex --------------------------------------------------------


def test_distribuicao(texto_md: str) -> None:
    fatos = extrair_fatos(texto_md)
    assert [(d.nome, d.questoes, d.peso_questao) for d in fatos.distribuicao] == [
        ("Língua Portuguesa", 10, 1.0),
        ("Raciocínio Lógico", 5, 1.0),
        ("Legislação Municipal", 5, 1.0),
        ("Conhecimentos Específicos", 30, 2.0),
    ]
    assert all(d.fonte == "edital §6.2" for d in fatos.distribuicao)


def test_distribuicao_no_texto_do_pdf() -> None:
    # No PDF o parágrafo 6.2 vem em três linhas: as linhas de um parágrafo são reunidas.
    pdf = pytest.importorskip("aprovaos.dominio.pdf")
    if not FIXTURE_PDF.exists():
        pytest.skip("fixture PDF ainda não gerada (passo 3 da V2)")
    fatos = extrair_fatos(pdf.extrair_texto(FIXTURE_PDF.read_bytes()))
    assert [(d.nome, d.questoes) for d in fatos.distribuicao] == [
        ("Língua Portuguesa", 10),
        ("Raciocínio Lógico", 5),
        ("Legislação Municipal", 5),
        ("Conhecimentos Específicos", 30),
    ]
    assert fatos.regra.fonte == "edital §6.1, §6.3"
    assert fatos.cabecalho.banca == "FUNDAÇÃO DE APOIO À UNIOESTE"
    assert fatos.cabecalho.data_prova == date(2026, 11, 15)


def test_distribuicao_ausente() -> None:
    fatos = extrair_fatos("EDITAL Nº 02/2026\n6.1 Prova objetiva com 40 questões.")
    assert fatos.distribuicao == []


def test_regra_correcao(texto_md: str) -> None:
    regra = extrair_fatos(texto_md).regra
    assert regra.tipo_item == "multipla_escolha"
    assert regra.alternativas == 5
    assert regra.anula_por_erro is False
    assert regra.minimo_global == "50 % do total de pontos"
    assert regra.minimo_por_materia == "nota zero elimina"
    assert regra.fonte == "edital §6.1, §6.3"


def test_regra_correcao_certo_errado() -> None:
    texto = (
        "5. DA PROVA OBJETIVA\n"
        "5.1 A prova terá 120 itens do tipo CERTO ou ERRADO; uma resposta errada anula uma "
        "resposta certa."
    )
    regra = extrair_fatos(texto).regra
    assert regra.tipo_item == "certo_errado"
    assert regra.alternativas is None
    assert regra.anula_por_erro is True
    assert regra.fonte == "edital §5.1"


def test_regra_desconhecida() -> None:
    regra = extrair_fatos("EDITAL\n1. Das inscrições.").regra
    assert regra.tipo_item == "desconhecido"
    assert regra.alternativas is None
    assert regra.anula_por_erro == "desconhecido"
    assert regra.minimo_global == "desconhecido"
    assert regra.minimo_por_materia == "desconhecido"


def test_cabecalho(texto_md: str) -> None:
    cabecalho = extrair_fatos(texto_md).cabecalho
    assert cabecalho.orgao == "CÂMARA MUNICIPAL DE CASCAVEL — ESTADO DO PARANÁ"
    assert cabecalho.cargo == "ASSESSOR DE GABINETE"
    assert cabecalho.banca == "FUNDAÇÃO DE APOIO À UNIOESTE"
    assert cabecalho.edital == "01/2026"
    assert cabecalho.data_prova == date(2026, 11, 15)
    assert cabecalho.fonte == "edital §1.1, §1.2, §6.5"


def test_cabecalho_desconhecido() -> None:
    cabecalho = extrair_fatos("texto qualquer\nsem nada útil.").cabecalho
    assert cabecalho.orgao == "desconhecido"
    assert cabecalho.cargo == "desconhecido"
    assert cabecalho.banca == "desconhecido"
    assert cabecalho.edital == "desconhecido"
    assert cabecalho.data_prova is None


def test_etapas(texto_md: str) -> None:
    assert extrair_fatos(texto_md).etapas == [
        Etapa(nome="objetiva", pontos=80, quem_faz=None, fonte="edital §6.2"),
        Etapa(nome="discursiva", pontos=20, quem_faz="60 primeiros", fonte="edital §6.4"),
    ]


def test_etapas_sem_distribuicao_nem_discursiva() -> None:
    etapas = extrair_fatos("EDITAL\n1. Das inscrições.").etapas
    assert len(etapas) == 1
    assert etapas[0].nome == "objetiva"
    assert etapas[0].pontos == "desconhecido"


def test_fonte_conteudo_programatico(texto_md: str) -> None:
    assert fonte_conteudo_programatico(texto_md) == "edital Anexo I"
    assert fonte_conteudo_programatico("CONTEÚDO PROGRAMÁTICO\nX: 1. a.") == (
        "edital (conteúdo programático)"
    )
    assert fonte_conteudo_programatico("nada") == "edital (conteúdo programático)"
