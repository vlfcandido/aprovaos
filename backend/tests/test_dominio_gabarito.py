# O que é: testes do passo 7 da V3 — leitura do gabarito definitivo da Cebraspe (`dominio/
# gabarito.py`). Quando ler: ao mudar `ler_gabarito_cebraspe` ou os fixtures reais de gabarito.
from pathlib import Path

import pytest

from aprovaos.dominio.erros import GabaritoNaoReconhecido
from aprovaos.dominio.gabarito import EntradaGabarito, ler_gabarito_cebraspe
from aprovaos.dominio.pdf import extrair_texto

RAIZ = Path(__file__).resolve().parents[2]
_PROVAS = RAIZ / "knowledge/provas"

# Gabarito definitivo do CARGO 9 (Analista Judiciário — Direito) da TJ_PA_25_SERVIDOR: mesmo
# fixture citado no passo 6 (`test_dominio_prova.py`), agora o PDF do gabarito (não o da prova).
FIXTURE_GAB_TJ_PA = (
    _PROVAS
    / "TJ_PA_25_SERVIDOR"
    / "EF721EA56FA324A5AE5E9F7A8FD2FE4800E803E772BC6D03E0403D1B61632F72.pdf"
)
FIXTURE_GAB_STJ = _PROVAS / "STJ_24" / "GAB_DEFINITIVO_018_STJ_019_01.PDF"
FIXTURE_GAB_TRT10_012 = _PROVAS / "TRT10_24" / "Gab_Definitivo_050_TRT10_012_01.pdf"
FIXTURE_GAB_TRT10_013 = _PROVAS / "TRT10_24" / "Gab_Definitivo_050_TRT10_013_01.pdf"
# Gabarito de múltipla escolha A–E — fora do escopo desta fatia (decisão 2 do passo 6); serve só
# para provar que a função não engole formato que não entende (decisão 6 do brief do passo 7).
FIXTURE_GAB_TJCE_ME = _PROVAS / "TJ_CE_23_SERVIDOR" / "GAB_DEFINITIVO_820_TJCE_SERVIDOR_001_01.PDF"

# N medido no gabarito real do CARGO 9 da TJ_PA: itens 51 a 120 (70 entradas) — o mesmo N do
# passo 6; o preenchimento "0" fora do intervalo não é entrada (conferido linha a linha no PDF).
N_ITENS_TJ_PA = 70

# Itens que o quadro do gabarito real da TJ_PA marca com "X" (Obs.: "( X ) item anulado."),
# conferidos linha a linha no texto extraído do PDF.
ANULADOS_TJ_PA = {75, 104, 105, 108, 112}


def _texto_do_pdf(caminho: Path) -> str:
    return extrair_texto(caminho.read_bytes())


def test_le_gabarito_real() -> None:
    """O gabarito real do CARGO 9 da TJ_PA tem 70 entradas, cada uma com valor C/E ou None."""
    gabarito = ler_gabarito_cebraspe(_texto_do_pdf(FIXTURE_GAB_TJ_PA))
    assert len(gabarito) == N_ITENS_TJ_PA
    assert set(gabarito) == set(range(51, 51 + N_ITENS_TJ_PA))
    for entrada in gabarito.values():
        assert entrada.valor in {"C", "E", None}


def test_anulado() -> None:
    """Item anulado no gabarito real (marcado "X" no quadro) vira valor=None, status=anulado."""
    gabarito = ler_gabarito_cebraspe(_texto_do_pdf(FIXTURE_GAB_TJ_PA))
    anulados = {numero for numero, entrada in gabarito.items() if entrada.status == "anulado"}
    assert anulados == ANULADOS_TJ_PA
    for numero in ANULADOS_TJ_PA:
        assert gabarito[numero] == EntradaGabarito(
            valor=None, status="anulado", valor_preliminar=None
        )


def test_alterado() -> None:
    """Item com gabarito preliminar e definitivo diferentes vira status=alterado.

    Nenhum dos quatro gabaritos reais desta fatia traz uma seção "GABARITO PRELIMINAR" separada
    da definitiva (são documentos só de gabarito definitivo — ver `passo-7-report.md`); por isso
    este caso usa texto sintético, no formato de grade que os quatro arquivos reais usam.
    """
    texto = """\
GABARITO PRELIMINAR
1 2
C E
GABARITOS OFICIAIS DEFINITIVOS
1 2
C C
"""
    gabarito = ler_gabarito_cebraspe(texto)
    assert gabarito[1] == EntradaGabarito(valor="C", status="definitivo", valor_preliminar=None)
    assert gabarito[2] == EntradaGabarito(valor="C", status="alterado", valor_preliminar="E")


def test_item_fora_do_gabarito() -> None:
    """Consultar um item que não está no gabarito devolve `None` (decisão é do curador)."""
    gabarito = ler_gabarito_cebraspe(_texto_do_pdf(FIXTURE_GAB_TJ_PA))
    assert gabarito.get(50) is None
    assert gabarito.get(121) is None
    assert gabarito.get(999) is None


def test_formato_nao_reconhecido_levanta_erro() -> None:
    """Um gabarito de múltipla escolha A–E não tem a grade C/E — a função para, não devolve {}."""
    with pytest.raises(GabaritoNaoReconhecido):
        ler_gabarito_cebraspe(_texto_do_pdf(FIXTURE_GAB_TJCE_ME))


def test_le_gabaritos_reais_de_conferencia() -> None:
    """Os outros três gabaritos C/E reais da fatia: mesma contagem e anulados conferidos no PDF."""
    casos = [
        (FIXTURE_GAB_STJ, 70, {85, 97}),
        (FIXTURE_GAB_TRT10_012, 70, {53, 55, 75}),
        (FIXTURE_GAB_TRT10_013, 70, {53, 55, 75}),
    ]
    for caminho, n_esperado, anulados_esperados in casos:
        gabarito = ler_gabarito_cebraspe(_texto_do_pdf(caminho))
        assert len(gabarito) == n_esperado, caminho.name
        anulados = {n for n, entrada in gabarito.items() if entrada.status == "anulado"}
        assert anulados == anulados_esperados, caminho.name
