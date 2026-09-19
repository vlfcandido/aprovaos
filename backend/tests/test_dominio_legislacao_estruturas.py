# O que é: testes red-first das quatro estruturas da P-40 (docs/PENDENCIAS.md) que
# `dominio/legislacao.extrair_artigo` ainda não tratava — título de Seção/Capítulo em Title
# Case, parágrafo com sufixo de letra, alínea direto sob o caput e anotação "Vigência
# encerrada" órfã — contra os HTMLs reais em `knowledge/fixtures/juridico/`. Quando ler: ao
# mexer em `_eh_titulo_estrutural`, `_PADRAO_PARAGRAFO`, `alvo_alinea` ou
# `_PADRAO_VIGENCIA_SEM_PARENTESES`.
from pathlib import Path

from aprovaos.dominio.legislacao import extrair_artigo
from aprovaos.motor.fontes.planalto import decodificar_html

RAIZ = Path(__file__).resolve().parents[2]
_JURIDICO = RAIZ / "knowledge/fixtures/juridico"


def _ler(nome: str) -> str:
    """Lê um HTML compilado do Planalto como bytes e decodifica pela mesma regra do coletor
    (`cp1252` na maioria; UTF-16 com BOM para a Lei 11.340 — ver `Achado 1` do
    `knowledge/fixtures/juridico/LEIA-ME.md`)."""
    return decodificar_html((_JURIDICO / nome).read_bytes())


HTML_LEI_8429 = _ler("lei8429_planalto_compilada.htm")
HTML_LEI_11340 = _ler("lei11340_planalto_compilada.htm")


# --- (a) título de Seção/Capítulo em Title Case entre artigos --------------------------------


def test_artigo_9_da_lei_8429_atravessa_titulo_secao_ii_em_title_case() -> None:
    """`"Seção II\\nDos Atos de Improbidade... Erário"` (entre os arts. 9º e 10) não é dispositivo
    do art. 9º — o caput vigente (o de enriquecimento ilícito) é lido normalmente."""
    artigo = extrair_artigo(HTML_LEI_8429, "9")

    assert artigo.caput.texto.startswith(
        "Art. 9º Constitui ato de improbidade administrativa importando em enriquecimento ilícito"
    )
    textos = [artigo.caput.texto, *(i.texto for i in artigo.incisos)]
    assert not any("Seção II" in t or "Prejuízo ao Erário" in t for t in textos)


def test_artigo_10_da_lei_8429_atravessa_subtitulo_sem_a_palavra_secao() -> None:
    """Entre os arts. 10 e 11 o Planalto intercala só o subtítulo, sem a palavra "Seção" —
    `"Dos Atos de Improbidade Administrativa Decorrentes de Concessão ou Aplicação Indevida de
    Benefício Financeiro ou Tributário"` — e mesmo assim não pode virar dispositivo do art. 10."""
    artigo = extrair_artigo(HTML_LEI_8429, "10")

    assert artigo.caput.texto.startswith(
        "Art. 10. Constitui ato de improbidade administrativa que causa lesão ao erário"
    )
    textos = [artigo.caput.texto, *(i.texto for i in artigo.incisos)]
    assert not any("Benefício Financeiro ou Tributário" in t for t in textos)


def test_artigo_11_da_lei_8429_atravessa_capitulo_iii_misto_de_caixa() -> None:
    """`"CAPÍTULO III Das Penas"` mistura CAIXA ALTA ("CAPÍTULO III") com Title Case ("Das
    Penas") na mesma linha — o heurístico antigo (só caixa alta) não reconhecia o parágrafo
    inteiro como título por causa de "Das Penas"."""
    artigo = extrair_artigo(HTML_LEI_8429, "11")

    assert artigo.caput.texto.startswith(
        "Art. 11. Constitui ato de improbidade administrativa que atenta contra os princípios "
        "da administração pública"
    )
    textos = [artigo.caput.texto, *(i.texto for i in artigo.incisos)]
    assert not any("CAPÍTULO III" in t or "Das Penas" in t for t in textos)


def test_artigo_24_da_lei_11340_atravessa_secao_iv_e_rubrica_sem_palavra_chave() -> None:
    """Entre os arts. 24 e 24-A da Lei Maria da Penha vêm dois parágrafos de título seguidos:
    `"Seção IV"` sozinho e, na sequência, a rubrica `"Do Crime de Descumprimento de Medidas
    Protetivas de Urgência..."` (sem a palavra "Seção"/"Capítulo") — os dois têm de ser
    atravessados para o art. 24 fechar no parágrafo único dele."""
    artigo = extrair_artigo(HTML_LEI_11340, "24")

    assert artigo.caput.texto.startswith("Art. 24.")
    assert len(artigo.paragrafos) == 1
    assert artigo.paragrafos[0].identificador == "Parágrafo único."
    textos = [artigo.caput.texto, artigo.paragrafos[0].texto]
    assert not any("Seção IV" in t or "Descumprimento de Medidas Protetivas" in t for t in textos)


