# O que é: testes do passo 6 da V3 (segmentação C/E) e do passo 1 da V3b (segmentação A–E) —
# `dominio/prova.py`. Quando ler: ao mudar `segmentar_cebraspe`/`segmentar_multipla_escolha` ou
# os fixtures reais da TJ_PA (C/E) e da TJ_CE_23_SERVIDOR (A–E).
from pathlib import Path

import pytest

from aprovaos.dominio.erros import SegmentacaoAmbigua
from aprovaos.dominio.gabarito import ler_gabarito_multipla_escolha
from aprovaos.dominio.pdf import extrair_texto
from aprovaos.dominio.prova import segmentar_cebraspe, segmentar_multipla_escolha

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_PROVA = (
    RAIZ
    / "knowledge/provas/TJ_PA_25_SERVIDOR"
    / "C15F414E0E91EF109220A73BDF53B232C4466F64770A91E715C56DCB94131F41.pdf"
)
FIXTURE_PROVA_ME = RAIZ / "knowledge/provas/TJ_CE_23_SERVIDOR/820_TJCE_SERVIDOR_001_01.PDF"

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


# --- Passo 1 da fatia V3b: segmentação Cebraspe A–E (múltipla escolha) --------------------------
# Caderno real TJ_CE_23_SERVIDOR (Técnico Judiciário, único cargo, nível médio). Gabarito
# definitivo lista as questões 21 a 60 (40 entradas) — conferido em
# `.superpowers/sdd/V3b-multipla-escolha/passo-1-report.md`.
N_QUESTOES_TJ_CE = 40

# As cinco questões do caderno real cujo enunciado começa com o artigo "A" seguido de palavra
# maiúscula ("A República...", "A forma de extinção...", "A encampação...", "A Resolução...",
# "A vedação...") — a mesma forma da alternativa A ("A <texto>"). Achado do passo 1: sem
# resolver por eliminação posicional, esse "A" do enunciado seria lido como a alternativa A.
_QUESTOES_COM_ARTIGO_A_NO_ENUNCIADO = [21, 32, 33, 40, 46]


def _texto_do_pdf_me(caminho: Path) -> str:
    return extrair_texto(caminho.read_bytes())


def test_segmenta_caderno_real_multipla_escolha() -> None:
    """O caderno real da TJ_CE tem exatamente 40 questões, numeradas de 21 a 60 sem buracos."""
    itens = segmentar_multipla_escolha(_texto_do_pdf_me(FIXTURE_PROVA_ME))
    assert len(itens) == N_QUESTOES_TJ_CE
    numeros = [item.numero_item for item in itens]
    assert numeros == list(range(21, 21 + N_QUESTOES_TJ_CE))


def test_toda_questao_tem_cinco_alternativas_em_ordem() -> None:
    """Cada questão do caderno real tem exatamente as alternativas A, B, C, D, E, nessa ordem."""
    itens = segmentar_multipla_escolha(_texto_do_pdf_me(FIXTURE_PROVA_ME))
    for item in itens:
        letras = [alternativa.letra for alternativa in item.alternativas]
        assert letras == ["A", "B", "C", "D", "E"], item.numero_item
        for alternativa in item.alternativas:
            assert alternativa.texto.strip(), (item.numero_item, alternativa.letra)


def test_artigo_a_no_enunciado_nao_vira_alternativa_falsa() -> None:
    """O "A" do início do enunciado não rouba o lugar da alternativa A de verdade.

    Achado do passo 1: 5 das 40 questões do caderno real começam com o artigo "A" seguido de
    palavra maiúscula — a mesma forma de uma linha de alternativa. A alternativa A de verdade tem
    de ser a que vem depois do enunciado inteiro, nunca a primeira palavra dele.
    """
    itens = {
        item.numero_item: item
        for item in segmentar_multipla_escolha(_texto_do_pdf_me(FIXTURE_PROVA_ME))
    }
    esperado = {
        21: "é exercido exclusivamente de forma indireta",
        32: "caducidade.",
        33: "serviço prestado de forma inadequada ou deficiente",
        40: "criou o Laboratório de Inovação",
        46: "apenas às partes, aos membros da Defensoria Pública",
    }
    for numero in _QUESTOES_COM_ARTIGO_A_NO_ENUNCIADO:
        item = itens[numero]
        assert item.enunciado.startswith("A "), numero
        alternativa_a = item.alternativas[0]
        assert alternativa_a.letra == "A"
        assert alternativa_a.texto.startswith(esperado[numero]), numero


def test_multipla_escolha_item_em_varias_linhas_e_enunciado_com_instrucao_embutida() -> None:
    """Enunciado quebrado em linhas vira um texto só; a instrução final fica no próprio enunciado.

    Achado do passo 1: o caderno real não usa comando compartilhado entre questões — a instrução
    ("assinale a opção correta") está embutida no fim do enunciado de cada questão.
    """
    texto = """\
Questão 1
Acerca do controle de constitu-
cionalidade, assinale a opção
correta.
A a ação direta de inconstitucionalidade é de competência do
Superior Tribunal de Justiça.
B o controle difuso pode ser exercido por qualquer juízo.
C a súmula vinculante dispensa qualquer forma de publicação.
D o controle preventivo é exercido exclusivamente pelo Poder
Judiciário.
E a ação declaratória de constitucionalidade não admite medida
cautelar.
"""
    itens = segmentar_multipla_escolha(texto)
    assert len(itens) == 1
    item = itens[0]
    assert item.numero_item == 1
    assert item.enunciado == (
        "Acerca do controle de constitucionalidade, assinale a opção correta."
    )
    assert "-" not in item.enunciado
    letras = [alternativa.letra for alternativa in item.alternativas]
    assert letras == ["A", "B", "C", "D", "E"]
    assert item.alternativas[0].texto == (
        "a ação direta de inconstitucionalidade é de competência do Superior Tribunal de Justiça."
    )
    assert item.alternativas[4].texto == (
        "a ação declaratória de constitucionalidade não admite medida cautelar."
    )


def test_multipla_escolha_ignora_cabecalho_secao_e_espaco_livre() -> None:
    """Cabeçalho com código numérico, marcador de seção e "Espaço livre" não viram conteúdo."""
    texto = """\
82000101135697 CEBRASPE – TJ/CE – SERVIDOR – Edital: 2023
-- CONHECIMENTOS ESPECÍFICOS --
Questão 1
Assinale a opção correta.
A primeira alternativa.
B segunda alternativa.
C terceira alternativa.
D quarta alternativa.
E quinta alternativa.
Espaço livre
82000101135697 CEBRASPE – TJ/CE – SERVIDOR – Edital: 2023
Questão 2
Assinale a opção correta.
A primeira alternativa.
B segunda alternativa.
C terceira alternativa.
D quarta alternativa.
E quinta alternativa.
"""
    itens = segmentar_multipla_escolha(texto)
    assert [item.numero_item for item in itens] == [1, 2]
    for item in itens:
        assert "CEBRASPE" not in item.enunciado
        assert "Espaço livre" not in item.enunciado


def test_multipla_escolha_sem_cinco_alternativas_levanta_erro() -> None:
    """Uma questão sem as cinco alternativas reconhecíveis é estrutura não coberta — para."""
    texto = """\
Questão 1
Assinale a opção correta.
A primeira alternativa.
B segunda alternativa.
C terceira alternativa.
D quarta alternativa.
"""
    with pytest.raises(SegmentacaoAmbigua):
        segmentar_multipla_escolha(texto)


def test_multipla_escolha_bate_com_o_numero_de_entradas_do_gabarito_no_caderno_real() -> None:
    """A contagem de questões segmentadas bate com a do gabarito real (regra de ouro da fatia)."""
    caminho_gabarito = (
        RAIZ / "knowledge/provas/TJ_CE_23_SERVIDOR" / "GAB_DEFINITIVO_820_TJCE_SERVIDOR_001_01.PDF"
    )
    itens = segmentar_multipla_escolha(_texto_do_pdf_me(FIXTURE_PROVA_ME))
    gabarito = ler_gabarito_multipla_escolha(_texto_do_pdf_me(caminho_gabarito))
    assert {item.numero_item for item in itens} == set(gabarito)
