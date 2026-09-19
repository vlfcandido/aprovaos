# O que é: testes do passo 6 da V3 — segmentação determinística de caderno Cebraspe C/E
# (`dominio/prova.py`). Quando ler: ao mudar `segmentar_cebraspe` ou o fixture real da TJ_PA.
from pathlib import Path

import pytest

from aprovaos.dominio.erros import SegmentacaoAmbigua
from aprovaos.dominio.pdf import extrair_texto
from aprovaos.dominio.prova import segmentar_cebraspe

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_PROVA = (
    RAIZ
    / "knowledge/provas/TJ_PA_25_SERVIDOR"
    / "C15F414E0E91EF109220A73BDF53B232C4466F64770A91E715C56DCB94131F41.pdf"
)

# N medido no gabarito definitivo do CARGO 9 (Analista Judiciário — Direito) da TJ_PA_25_SERVIDOR:
# o gabarito lista os itens 51 a 120 (70 entradas; o resto do quadro é preenchimento com "0",
# sem item correspondente) — conferido em `.superpowers/sdd/V3-questoes-cebraspe/passo-6-report.md`.
N_ITENS_TJ_PA = 70


def _texto_do_pdf(caminho: Path) -> str:
    return extrair_texto(caminho.read_bytes())


def test_segmenta_caderno_real() -> None:
    """O caderno real da TJ_PA tem exatamente 70 itens, numerados de 51 a 120 sem buracos."""
    itens = segmentar_cebraspe(_texto_do_pdf(FIXTURE_PROVA))
    assert len(itens) == N_ITENS_TJ_PA
    numeros = [item.numero_item for item in itens]
    assert numeros == list(range(51, 51 + N_ITENS_TJ_PA))


# Os quatro itens do caderno real da TJ_PA cujo bloco tem uma narrativa de situação hipotética
# sem marcador "Texto para..." entre o fim do próprio item e o comando seguinte (achado da
# rodada de correção 1; ver `passo-6-report.md`). Cada entrada é
# (numero_do_item, primeira_frase_da_narrativa_que_não_pode_grudar, itens_que_a_narrativa_apoia).
_CASOS_DE_NARRATIVA_IMPLICITA = [
    (
        99,
        "Em ação indenizatória ajuizada por Maria, vítima do compartilhamento não autorizado "
        "de imagens íntimas suas em um aplicativo de mensagens",
        [100, 101, 102, 103],
    ),
    (
        106,
        "João, de 19 anos de idade, e Pedro, de 17 anos de idade, assaltaram uma loja de "
        "eletrônicos",
        [107, 108, 109, 110, 111],
    ),
    (
        111,
        "Durante uma operação policial, Roberto, funcionário público, foi flagrado recebendo "
        "R$ 5 mil de um empresário",
        [112, 113, 114, 115, 116],
    ),
    (
        116,
        "Lucas invadiu a residência de sua ex-namorada, Sandra, durante a madrugada",
        [117, 118, 119, 120],
    ),
]


def test_narrativa_implicita_nao_gruda_no_enunciado_do_item_anterior() -> None:
    """A narrativa de situação hipotética sem marcador não fica no `enunciado` de quem a antecede.

    Achado da rodada de correção 1 (revisão do PDF real, página 4): sem marcador "Texto para...",
    a narrativa que introduz os itens seguintes ficava colada ao enunciado do item anterior.
    """
    itens = {item.numero_item: item for item in segmentar_cebraspe(_texto_do_pdf(FIXTURE_PROVA))}
    for numero, primeira_frase_da_narrativa, _itens_apoiados in _CASOS_DE_NARRATIVA_IMPLICITA:
        assert primeira_frase_da_narrativa not in itens[numero].enunciado, numero


def test_narrativa_implicita_vira_texto_apoio_dos_itens_seguintes() -> None:
    """A narrativa não marcada vira `texto_apoio` dos itens que vêm depois do comando seguinte."""
    itens = {item.numero_item: item for item in segmentar_cebraspe(_texto_do_pdf(FIXTURE_PROVA))}
    for _numero, primeira_frase_da_narrativa, itens_apoiados in _CASOS_DE_NARRATIVA_IMPLICITA:
        for apoiado in itens_apoiados:
            item = itens[apoiado]
            assert item.texto_apoio is not None, apoiado
            assert item.texto_apoio.startswith(primeira_frase_da_narrativa), apoiado
            assert item.texto_apoio_itens == itens_apoiados, apoiado


def test_comando_vale_ate_o_proximo() -> None:
    """Um comando vale para todos os itens seguintes, até o próximo comando aparecer."""
    texto = """\
Com base na Lei nº 14.133/2021, julgue os itens subsequentes.
1 A modalidade de licitação diálogo competitivo é restrita a
contratações que envolvam inovação tecnológica.
2 O pregão é obrigatório para a contratação de serviços comuns.
3 A dispensa de licitação independe de justificativa escrita.
Acerca dos princípios da administração pública, julgue o item a seguir.
4 A impessoalidade veda a promoção pessoal de agentes públicos.
"""
    itens = segmentar_cebraspe(texto)
    assert [item.numero_item for item in itens] == [1, 2, 3, 4]
    assert itens[0].comando == "Com base na Lei nº 14.133/2021, julgue os itens subsequentes."
    assert itens[1].comando == itens[0].comando
    assert itens[2].comando == itens[0].comando
    assert (
        itens[3].comando == "Acerca dos princípios da administração pública, julgue o item a "
        "seguir."
    )


def test_texto_de_apoio_por_intervalo() -> None:
    """ "Texto para os itens X e Y" vira `texto_apoio` só dos itens do intervalo."""
    texto = """\
Texto para os itens 58 e 59
A Lei nº 14.133/2021 estabelece normas gerais de licitação e
contratação para as administrações públicas diretas, autárquicas e
fundacionais da União, dos estados, do Distrito Federal e dos municípios.
Com base nesse texto, julgue os itens que se seguem.
58 O diálogo competitivo é modalidade de licitação restrita a
contratações que envolvam inovação tecnológica ou técnica.
59 A modalidade pregão pode ser usada para a contratação de obras
de engenharia de alta complexidade.
Acerca dos contratos administrativos, julgue o item a seguir.
60 A subcontratação total do objeto contratual é sempre permitida.
"""
    itens = segmentar_cebraspe(texto)
    assert [item.numero_item for item in itens] == [58, 59, 60]
    item58, item59, item60 = itens
    assert item58.texto_apoio_itens == [58, 59]
    assert item59.texto_apoio_itens == [58, 59]
    assert item58.texto_apoio == item59.texto_apoio
    assert item58.texto_apoio is not None
    assert item58.texto_apoio.startswith("A Lei nº 14.133/2021")
    assert item60.texto_apoio is None
    assert item60.texto_apoio_itens == []


def test_item_em_varias_linhas() -> None:
    """Um enunciado quebrado em três linhas pelo PDF vira um `enunciado` só, sem hífen de quebra."""
    texto = """\
Julgue o item a seguir.
1 O controle de constitu-
cionalidade concentrado é de competência exclu-
siva do Supremo Tribunal Federal.
"""
    itens = segmentar_cebraspe(texto)
    assert len(itens) == 1
    assert itens[0].enunciado == (
        "O controle de constitucionalidade concentrado é de competência exclusiva do Supremo "
        "Tribunal Federal."
    )
    assert "-" not in itens[0].enunciado
    assert "\n" not in itens[0].enunciado


def test_segmentacao_bate_com_gabarito_nos_cadernos_de_conferencia() -> None:
    """Conferência (não obrigatória, decisão 3): três cadernos C/E extras, mesma contagem do PDF.

    `TJ_CE_23_SERVIDOR` não entra aqui — o gabarito dele é de múltipla escolha (A–E), fora do
    escopo desta fatia (decisão 2); ver `passo-6-report.md` para o detalhe.
    """
    casos = [
        ("STJ_24/018_STJ_019_01.PDF", 70),
        ("TRT10_24/050_TRT10_012_01.pdf", 70),
        ("TRT10_24/050_TRT10_013_01.pdf", 70),
    ]
    for nome_relativo, n_esperado in casos:
        caminho = RAIZ / "knowledge/provas" / nome_relativo
        itens = segmentar_cebraspe(_texto_do_pdf(caminho))
        assert len(itens) == n_esperado, nome_relativo
        numeros = [item.numero_item for item in itens]
        assert numeros == list(range(numeros[0], numeros[0] + len(numeros))), nome_relativo


def test_mais_de_duas_fronteiras_de_comando_no_bloco_do_item_levanta_erro() -> None:
    """Um bloco com 3+ fronteiras candidatas é estrutura fora do padrão — não adivinha, para."""
    texto = """\
Comando inicial. Julgue os itens a seguir.
1 Primeira sentença do item.
Narrativa um que não é apoio marcado.
Narrativa dois, ainda sem julgue, mas fecha frase.
Comando novo. Julgue os itens seguintes.
2 Segundo item.
"""
    with pytest.raises(SegmentacaoAmbigua):
        segmentar_cebraspe(texto)


def test_mais_de_uma_fronteira_no_bloco_de_texto_de_apoio_levanta_erro() -> None:
    """O bloco entre o marcador "Texto para..." e o comando só tolera uma fronteira conhecida."""
    texto = """\
Texto para os itens 1 e 2
Corpo do texto de apoio.
Narrativa extra que também termina em ponto.
Comando do texto de apoio. Julgue os itens a seguir.
1 Primeiro item do intervalo.
2 Segundo item do intervalo.
"""
    with pytest.raises(SegmentacaoAmbigua):
        segmentar_cebraspe(texto)


def test_ignora_cabecalho_e_rodape() -> None:
    """Cabeçalho repetido e número de página isolado não viram item nem entram no texto."""
    texto = """\
CEBRASPE | TJ/PA – Aplicação: 2025
Julgue os itens a seguir.
1 A prescrição é instituto de direito material.
7
2 A decadência não se sujeita a suspensão nem a interrupção.
"""
    itens = segmentar_cebraspe(texto)
    assert [item.numero_item for item in itens] == [1, 2]
    assert itens[0].enunciado == "A prescrição é instituto de direito material."
    assert itens[1].enunciado == "A decadência não se sujeita a suspensão nem a interrupção."
    for item in itens:
        assert "CEBRASPE" not in (item.comando or "")
        assert "CEBRASPE" not in item.enunciado
