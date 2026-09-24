# O que é: testes red-first do preceito secundário ("Pena - reclusão, de ... anos, e multa.") —
# a estrutura que todo tipo penal tem depois do caput e que `dominio/legislacao.extrair_artigo`
# recusava como forma desconhecida, contra o HTML real do Código Penal (Decreto-Lei 2.848/1940)
# em `knowledge/fixtures/juridico/`. Quando ler: ao mexer em `_PADRAO_PENA` ou em
# `ArtigoExtraido.penas`.
from pathlib import Path

from aprovaos.dominio.legislacao import extrair_artigo
from aprovaos.motor.fontes.planalto import decodificar_html

RAIZ = Path(__file__).resolve().parents[2]
_JURIDICO = RAIZ / "knowledge/fixtures/juridico"


def _ler(nome: str) -> str:
    """Lê um HTML compilado do Planalto como bytes e decodifica pela regra do coletor."""
    return decodificar_html((_JURIDICO / nome).read_bytes())


HTML_CP = _ler("del2848_planalto_compilada.htm")


def test_peculato_tem_o_preceito_secundario_do_caput_em_penas() -> None:
    """Art. 312 (peculato): a pena do caput é lida como pena, não como lacuna do artigo.

    O separador aqui é **hífen** (`"Pena - reclusão"`) e os limites vêm por extenso — a redação
    original de 1940, que nenhuma lei posterior reescreveu.
    """
    artigo = extrair_artigo(HTML_CP, "312")

    pena_do_caput = artigo.penas[0]
    assert pena_do_caput.tipo == "pena"
    assert pena_do_caput.identificador == "caput"
    assert pena_do_caput.texto == "Pena - reclusão, de dois a doze anos, e multa."


def test_corrupcao_passiva_usa_travessao_e_nao_hifen() -> None:
    """Art. 317 (corrupção passiva): o Planalto grafa o separador com **travessão** (U+2013) na
    redação dada pela Lei 10.763/2003 — a mesma estrutura, outro caractere."""
    artigo = extrair_artigo(HTML_CP, "317")

    assert artigo.penas[0].texto == ("Pena – reclusão, de 2 (dois) a 12 (doze) anos, e multa.")
    assert artigo.penas[0].redacao_de == "Redação dada pela Lei nº 10.763, de 12.11.2003"


def test_pena_de_paragrafo_fica_identificada_pelo_paragrafo_que_pune() -> None:
    """Art. 312, § 2º (peculato culposo): a pena que vem depois de um parágrafo pertence a ele —
    `identificador` guarda o rótulo do dispositivo punido, não um número de pena inventado."""
    artigo = extrair_artigo(HTML_CP, "312")

    assert [p.identificador for p in artigo.penas] == ["caput", "§ 2º"]
    assert artigo.penas[1].texto == "Pena - detenção, de três meses a um ano."


def test_preceito_secundario_nao_vira_inciso_nem_paragrafo() -> None:
    """A pena não pode poluir `incisos`/`paragrafos`: o art. 312 tem 3 parágrafos e 0 incisos,
    exatamente como o Código Penal os numera."""
    artigo = extrair_artigo(HTML_CP, "312")

    assert artigo.incisos == []
    assert [p.identificador for p in artigo.paragrafos] == ["§ 1º", "§ 2º", "§ 3º"]
    assert all("Pena" not in p.texto for p in artigo.paragrafos)


def test_pena_com_dois_pontos_tambem_e_reconhecida() -> None:
    """Art. 319-A: o Planalto separa com **dois pontos** (`"Pena: detenção..."`) nos tipos
    incluídos pela Lei 11.466/2007 — terceira grafia medida do mesmo dispositivo."""
    artigo = extrair_artigo(HTML_CP, "319-A")

    assert artigo.penas[0].texto == "Pena: detenção, de 3 (três) meses a 1 (um) ano."


def test_os_dez_artigos_de_crimes_contra_a_administracao_publica_extraem() -> None:
    """A receita `noc-dir-pen-07-crimes-contra` (`motor/dossie.py`) pede estes dez artigos; nove
    deles falhavam só pelo preceito secundário."""
    numeros = ["312", "313", "316", "317", "319", "321", "327", "330", "331", "333"]

    for numero in numeros:
        artigo = extrair_artigo(HTML_CP, numero)
        assert artigo.caput.texto.startswith("Art. ")


def test_rubrica_que_comeca_por_pena_continua_sendo_titulo_nao_dispositivo() -> None:
    """`"Pena de tentativa"` (rubrica do art. 14, parágrafo único) começa com a mesma palavra,
    mas não tem separador nem preceito — continua sendo título, nunca uma pena vazia."""
    artigo = extrair_artigo(HTML_CP, "14")

    assert all("Pena de tentativa" not in p.texto for p in artigo.penas)
    assert all("Pena de tentativa" not in p.texto for p in artigo.paragrafos)
