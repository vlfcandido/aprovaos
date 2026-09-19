# O que é: testes do passo 7 da V3 (gabarito C/E) e do passo 1 da V3b (gabarito A–E) —
# `dominio/gabarito.py`. Quando ler: ao mudar `ler_gabarito_cebraspe`/`ler_gabarito_multipla_
# escolha` ou os fixtures reais de gabarito.
from pathlib import Path

import pytest

from aprovaos.dominio.erros import GabaritoNaoReconhecido
from aprovaos.dominio.gabarito import (
    EntradaGabarito,
    EntradaGabaritoAlternativa,
    ler_gabarito_cebraspe,
    ler_gabarito_multipla_escolha,
)
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
    este caso usa texto sintético, no formato de grade que os quatro arquivos reais usam — com o
    rótulo de cada seção **depois** do próprio quadro, como a extração real produz (o rótulo
    "GABARITOS OFICIAIS DEFINITIVOS" sai depois da grade de números nos quatro PDFs reais, não
    antes; a leitura não depende da posição do rótulo, só de o item aparecer duas vezes com
    valores diferentes).
    """
    texto = """\
1 2
C E
GABARITO PRELIMINAR
1 2
C C
GABARITOS OFICIAIS DEFINITIVOS
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


# --- Passo 1 da fatia V3b: leitura do gabarito Cebraspe A–E (múltipla escolha) ------------------
# Mesmo gabarito real de `FIXTURE_GAB_TJCE_ME`, agora lido pela função A–E: 40 questões (21 a
# 60), com as questões 23, 27, 35, 38 e 40 marcadas "X" (anuladas) — conferido linha a linha no
# texto extraído do PDF (`.superpowers/sdd/V3b-multipla-escolha/passo-1-report.md`).
N_QUESTOES_TJ_CE = 40
ANULADAS_TJ_CE = {23, 27, 35, 38, 40}

# Os valores de todas as 40 questões, na ordem 21→60, conferidos na grade impressa do PDF
# ("D C X B D A X E E D D B D E X B C X A X" seguido de "A A B D C E B E E E B B A D C E E B A B").
_VALORES_TJ_CE = (
    "D C _ B D A _ E E D D B D E _ B C _ A _ A A B D C E B E E E B B A D C E E B A B"
).split()


def test_le_gabarito_multipla_escolha_real() -> None:
    """O gabarito real da TJ_CE tem 40 entradas (questões 21 a 60), cada uma A–E ou anulada."""
    gabarito = ler_gabarito_multipla_escolha(_texto_do_pdf(FIXTURE_GAB_TJCE_ME))
    assert len(gabarito) == N_QUESTOES_TJ_CE
    assert set(gabarito) == set(range(21, 21 + N_QUESTOES_TJ_CE))
    for entrada in gabarito.values():
        assert entrada.valor in {"A", "B", "C", "D", "E", None}


def test_anulada_multipla_escolha() -> None:
    """Questão anulada (marcada "X" no quadro) vira valor=None, status=anulado."""
    gabarito = ler_gabarito_multipla_escolha(_texto_do_pdf(FIXTURE_GAB_TJCE_ME))
    anuladas = {numero for numero, entrada in gabarito.items() if entrada.status == "anulado"}
    assert anuladas == ANULADAS_TJ_CE
    for numero in ANULADAS_TJ_CE:
        assert gabarito[numero] == EntradaGabaritoAlternativa(
            valor=None, status="anulado", valor_preliminar=None
        )


def test_valores_multipla_escolha_conferidos_na_grade() -> None:
    """Cada questão não anulada tem o valor exatamente igual ao impresso na grade do PDF."""
    gabarito = ler_gabarito_multipla_escolha(_texto_do_pdf(FIXTURE_GAB_TJCE_ME))
    for numero in range(21, 21 + N_QUESTOES_TJ_CE):
        valor_esperado = _VALORES_TJ_CE[numero - 21]
        if valor_esperado == "_":
            assert gabarito[numero].status == "anulado", numero
        else:
            assert gabarito[numero].valor == valor_esperado, numero
            assert gabarito[numero].status == "definitivo", numero


def test_alterado_multipla_escolha() -> None:
    """Questão com gabarito preliminar e definitivo diferentes vira status=alterado (sintético).

    Mesmo motivo do teste equivalente do gabarito C/E (`test_alterado`): o único gabarito A–E
    real desta fatia só tem grade definitiva, sem seção "GABARITO PRELIMINAR" separada.
    """
    texto = """\
1 2
A B
GABARITO PRELIMINAR
1 2
A A
GABARITOS OFICIAIS DEFINITIVOS
"""
    gabarito = ler_gabarito_multipla_escolha(texto)
    assert gabarito[1] == EntradaGabaritoAlternativa(
        valor="A", status="definitivo", valor_preliminar=None
    )
    assert gabarito[2] == EntradaGabaritoAlternativa(
        valor="A", status="alterado", valor_preliminar="B"
    )


def test_formato_nao_reconhecido_levanta_erro_multipla_escolha() -> None:
    """Um texto sem grade de gabarito A–E não devolve mapa vazio — a função para."""
    with pytest.raises(GabaritoNaoReconhecido):
        ler_gabarito_multipla_escolha("Isto não é um gabarito de forma nenhuma.")
