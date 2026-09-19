# O que é: testes red-first das quatro estruturas da P-40 (docs/PENDENCIAS.md) que
# `dominio/legislacao.extrair_artigo` ainda não tratava — título de Seção/Capítulo em Title
# Case, parágrafo com sufixo de letra, alínea direto sob o caput e anotação "Vigência
# encerrada" órfã — contra os HTMLs reais em `knowledge/fixtures/juridico/`. Quando ler: ao
# mexer em `_eh_titulo_estrutural`, `_PADRAO_PARAGRAFO`, `alvo_alinea` ou
# `_PADRAO_VIGENCIA_SEM_PARENTESES`.
from pathlib import Path

import pytest

from aprovaos.dominio.erros import EstruturaNaoTratada
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
HTML_LEI_6404 = _ler("lei6404_planalto_compilada.htm")
HTML_LEI_11101 = _ler("lei11101_planalto_compilada.htm")
HTML_CLT = _ler("clt_planalto_compilada.htm")


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


# --- (b) parágrafo com sufixo de letra ("§ 4º-A") ---------------------------------------------


def test_artigo_17_da_lei_8429_levanta_por_anomalia_real_no_6a_nao_pela_rede_de_seguranca() -> None:
    """Regressão consciente (revisão de 19/09/2026, não forçada): `extrair_artigo` volta a
    acusar `EstruturaNaoTratada` para o art. 17 inteiro — o "§ 4º-A" que a P-40 destravou
    continua sintaticamente correto (mesmo padrão provado pelo art. 6º da Lei 11.101/2005,
    teste seguinte), mas o **§ 6º-A real do Planalto tem um parêntese não fechado**: "...de 16
    de março de 2015 (Código de Processo Civil" — falta o `)` antes da anotação "(Incluído pela
    Lei nº 14.230, de 2021)" que vem logo depois (comparar com o § 6º-B, duas linhas abaixo no
    mesmo HTML, que fecha certinho: "...(Código de Processo Civil), bem como..."). Como a rede
    de segurança agora recusa qualquer §/inciso/alínea sem pontuação de fechamento (em vez de
    aceitar um trecho truncado como se fosse completo), esta anomalia real do documento oficial
    passa a impedir a extração do artigo inteiro — o comportamento aceito nesta revisão é
    declarar a lacuna, não servir o § 6º-A cortado no meio da frase."""
    with pytest.raises(EstruturaNaoTratada, match="Código de Processo Civil"):
        extrair_artigo(HTML_LEI_8429, "17")


def test_artigo_6_da_lei_11101_le_o_paragrafo_4_a_com_ponto() -> None:
    """Mesma estrutura, grafada com ponto final no identificador (`"§ 4º-A."`), na Lei
    11.101/2005 (recuperação judicial/falência)."""
    artigo = extrair_artigo(HTML_LEI_11101, "6")

    identificadores = [p.identificador for p in artigo.paragrafos]
    assert "§ 4º-A." in identificadores
    paragrafo_4a = next(p for p in artigo.paragrafos if p.identificador == "§ 4º-A.")
    assert paragrafo_4a.texto.startswith(
        "§ 4º-A. O decurso do prazo previsto no § 4º deste artigo sem a deliberação a respeito "
        "do plano de recuperação judicial"
    )


# --- (c) alínea listada direto sob o caput, sem inciso/parágrafo antecedente -------------------


def test_artigo_116_da_lei_6404_tem_alineas_direto_no_caput() -> None:
    """O art. 116 da Lei das S/A define "acionista controlador" com duas alíneas coladas no
    caput, sem nenhum inciso ou parágrafo entre elas — a alínea pertence ao caput."""
    artigo = extrair_artigo(HTML_LEI_6404, "116")

    assert artigo.caput.texto.startswith("Art. 116. Entende-se por acionista controlador")
    assert artigo.incisos == []
    alineas = {a.identificador: a for a in artigo.caput.alineas}
    assert set(alineas) == {"a", "b"}
    assert alineas["a"].texto.startswith("a) é titular de direitos de sócio")
    assert alineas["b"].texto.startswith("b) usa efetivamente seu poder")
    assert [p.identificador for p in artigo.paragrafos] == ["Parágrafo único."]


# --- (d) anotação "Vigência\nencerrada" órfã (sem parênteses) ----------------------------------


def test_artigo_477_da_clt_reconhece_redacao_dada_quebrada_em_duas_linhas() -> None:
    """Achado colateral ao destravar (d): o caput vigente do art. 477 só ficou visível depois
    da correção acima — e ele expôs uma quebra de linha do Planalto bem no meio da palavra-chave
    da anotação (`"(Redação \\r\\ndada pela Lei nº 13.467, de 2017)"`), que `_PADRAO_ANOTACAO`
    não reconhecia (esperava um único espaço, não `\\s+`). Sem esta correção, a trava "`redacao_de`
    continua vindo quando o Planalto informa a emenda/lei que deu a redação" quebraria bem no
    artigo que este trabalho existe para destravar."""
    artigo = extrair_artigo(HTML_CLT, "477")

    assert artigo.caput.redacao_de == "Redação dada pela Lei nº 13.467, de 2017"
    assert "Redação" not in artigo.caput.texto


def test_artigo_477_da_clt_engole_a_anotacao_vigencia_encerrada_orfa() -> None:
    """Depois de um parágrafo revogado (MPV 905/2019, revogada pela MPV 955/2020) sobra, fora do
    `<strike>`, só a anotação em duas palavras `"Vigência\\nencerrada"` — sem parênteses, então
    o padrão de anotação existente (que exige `(...)`) não a reconhece. Ela precisa sumir junto
    com o parágrafo todo revogado, não virar um "parágrafo sem forma reconhecida"."""
    artigo = extrair_artigo(HTML_CLT, "477")

    assert artigo.caput.texto.startswith("Art. 477.")
    textos = [artigo.caput.texto, *(p.texto for p in artigo.paragrafos)]
    assert not any(t.strip() in {"encerrada", "Vigência encerrada", "Vigência"} for t in textos)


# --- (e) inciso truncado não pode ser descartado como se fosse título (achado da revisão de
# 19/09/2026: `_eh_titulo_estrutural` passou a devolver `True` para *qualquer* bloco vigente sem
# pontuação final, não só para rótulo de divisão — um inciso cortado no meio da frase (linha
# continuada, célula de tabela virando `<p>`, pontuação que sobrou dentro do `<strike>` removido)
# desaparecia em silêncio em vez de acusar a lacuna) -------------------------------------------


def _html_artigo_com_inciso_truncado() -> str:
    """HTML mínimo, no formato "texto compilado" do Planalto, só para isolar este caso: um
    inciso (`IV`) sem pontuação de fechamento entre o caput do art. 99 e o caput do art. 100.

    Não é fixture de fonte externa (`ingestao-de-provas`/`monitor-de-fontes` proíbem isso) — é
    HTML sintético para testar a lógica pura do parser, o mesmo papel dos `<p>` avulsos que
    `test_dominio_legislacao.py::test_capitulo_e_secao_entre_artigos_nao_viram_dispositivo` já
    usa para o caso irmão (título de verdade, não dispositivo)."""
    return (
        "<p>Art. 99. É vedado ao servidor público, sob pena de demissão:</p>"
        "<p>IV - o servidor que, sem justa causa, deixar de</p>"
        "<p>Art. 100. Outro artigo qualquer.</p>"
    )


def test_inciso_truncado_sem_pontuacao_final_levanta_em_vez_de_sumir() -> None:
    """Um inciso cortado no meio da frase (sem `.`/`:`/`;` no fim) não é um título de divisão —
    tem corpo demais e não começa com rubrica nenhuma — e por isso não pode ser engolido pelo
    `continue` de `_eh_titulo_estrutural`; a lacuna tem de aparecer como `EstruturaNaoTratada`,
    nunca como um inciso silenciosamente incompleto nem como um sumiço."""
    html = _html_artigo_com_inciso_truncado()

    with pytest.raises(EstruturaNaoTratada):
        extrair_artigo(html, "99")
