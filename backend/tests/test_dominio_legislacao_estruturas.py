# O que é: testes red-first das estruturas do Planalto que `dominio/legislacao.extrair_artigo`
# não tratava — (a) título de Seção/Capítulo em Title Case, (b) parágrafo com sufixo de letra,
# (c) alínea direto sob o caput e (d) anotação "Vigência encerrada" órfã (P-40, 19/09/2026); (e)
# inciso sem travessão, (f) pontuação órfã do <strike>, (g) "Vide ..." sem parênteses e (h)
# rubrica longa do artigo seguinte (23/09/2026) — contra os HTMLs reais em
# `knowledge/fixtures/juridico/`. Quando ler: ao mexer em `_eh_titulo_estrutural`,
# `_PADRAO_PARAGRAFO`, `_PADRAO_INCISO`, `alvo_alinea`, `_eh_residuo_de_revogado`,
# `_eh_epigrafe_do_proximo_artigo` ou nos padrões de anotação sem parênteses.
from pathlib import Path

import pytest

from aprovaos.dominio.erros import EstruturaNaoTratada
from aprovaos.dominio.legislacao import extrair_artigo
from aprovaos.motor.fontes.planalto import decodificar_html

RAIZ = Path(__file__).resolve().parents[2]
_JURIDICO = RAIZ / "knowledge/fixtures/juridico"
_ADCT = "Vide art. 96 - ADCT"


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
HTML_CF = _ler("constituicao_planalto_compilada.htm")
HTML_CPP = _ler("del3689_planalto_compilada.htm")
HTML_CP = _ler("del2848_planalto_compilada.htm")


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


# --- (e) inciso que o Planalto grafa sem o travessão -------------------------------------------


def test_inciso_sem_travessao_do_artigo_52_da_cf_e_lido_como_inciso() -> None:
    """Na redação dada pela EC 45/2004, o Planalto perdeu o travessão do inciso II do art. 52 da
    CF: o parágrafo vigente começa em `"II processar e julgar os Ministros do Supremo Tribunal
    Federal, os membros do Conselho Nacional de Justiça..."` (a versão revogada, dentro do
    `<strike>` logo acima, traz o `"II - "` certinho). Sem reconhecer essa forma, o art. 52
    inteiro — competência privativa do Senado, pedido pela receita `noc-dir-con-06-6-organizacao`
    — virava lacuna."""
    artigo = extrair_artigo(HTML_CF, "52")

    inciso_ii = next(i for i in artigo.incisos if i.identificador == "II")
    assert inciso_ii.tipo == "inciso"
    assert inciso_ii.texto.startswith("II processar e julgar os Ministros do Supremo Tribunal")
    assert [i.identificador for i in artigo.incisos] == [
        "I", "II", "III", "IV", "V", "VI", "VII", "VIII",
        "IX", "X", "XI", "XII", "XIII", "XIV", "XV",
    ]  # fmt: skip


def test_inciso_com_sufixo_de_letra_e_sem_travessao_do_artigo_92_da_cf() -> None:
    """Art. 92, I-A (CNJ, incluído pela EC 45/2004): as duas variações no mesmo parágrafo —
    sufixo de letra no numeral **e** ausência do travessão (`"I-A o Conselho Nacional de
    Justiça;"`)."""
    artigo = extrair_artigo(HTML_CF, "92")

    assert [i.identificador for i in artigo.incisos] == [
        "I", "I-A", "II", "II-A", "III", "IV", "V", "VI", "VII",
    ]  # fmt: skip
    inciso_ia = next(i for i in artigo.incisos if i.identificador == "I-A")
    assert inciso_ia.texto == "I-A o Conselho Nacional de Justiça;"
    assert inciso_ia.redacao_de == "Incluído pela Emenda Constitucional nº 45, de 2004"


def test_numeral_romano_com_l_minusculo_nao_vira_inciso_inventado() -> None:
    """O contraponto que mantém a rede de segurança de pé: no CPP, art. 226, o Planalto escreveu
    `"Il - a pessoa, cujo reconhecimento se pretender..."` com **L minúsculo** no lugar do
    segundo `I`. Não é forma de inciso — é erro de digitação da fonte —, e o artigo continua
    sendo `EstruturaNaoTratada`, jamais um inciso com identificador `"I"` inventado por nós."""
    with pytest.raises(EstruturaNaoTratada, match="Il - a pessoa"):
        extrair_artigo(HTML_CPP, "226")


# --- (f) pontuação órfã que sobra fora do <strike> do trecho revogado --------------------------


def test_ponto_e_virgula_orfao_do_artigo_102_da_cf_nao_vira_dispositivo() -> None:
    """No art. 102, I, o `<p>` da alínea `c` revogada fecha o `;` **fora** do `<strike>`; tirado
    o texto revogado, sobra um parágrafo cujo conteúdo é só `";"`. Não é dispositivo truncado
    nem título: é resto de pontuação, e sumir é a única leitura honesta dele."""
    artigo = extrair_artigo(HTML_CF, "102")

    inciso_i = next(i for i in artigo.incisos if i.identificador == "I")
    assert [a.identificador for a in inciso_i.alineas] == [
        "a", "b", "c", "d", "e", "f", "g", "i", "j", "l", "m", "n", "o", "p", "q", "r",
    ]  # fmt: skip
    assert all(a.texto.strip() != ";" for a in inciso_i.alineas)


# --- (g) anotação "Vide ..." sem parênteses colada ao fim do dispositivo -----------------------


def test_vide_sem_parenteses_do_paragrafo_4_do_artigo_18_da_cf_vira_procedencia() -> None:
    """O § 4º do art. 18 da CF termina em `"...publicados na forma da lei."` e o Planalto cola,
    depois disso, um link sem parênteses: `"Vide art. 96 - ADCT"`. Grudada no texto, a nota
    fazia o parágrafo parecer truncado (não terminava mais em `.`/`:`/`;`) e derrubava o artigo
    inteiro — que a receita `noc-dir-con-05-5-organizacao` pede."""
    artigo = extrair_artigo(HTML_CF, "18")

    paragrafo_4 = next(p for p in artigo.paragrafos if p.identificador == "§ 4º")
    assert paragrafo_4.texto.endswith("apresentados e publicados na forma da lei.")
    assert _ADCT not in paragrafo_4.texto
    assert _ADCT in (paragrafo_4.redacao_de or "")


# --- (h) rubrica (nomen iuris) longa do artigo seguinte, colada ao fim deste -------------------


def test_rubrica_do_proximo_tipo_penal_nao_entra_no_artigo_anterior() -> None:
    """Entre os arts. 313 e 313-A do Código Penal, o Planalto põe a rubrica do próximo tipo —
    `"Inserção de dados falsos em sistema de informações"`, sete palavras, acima do limite do
    título curto. É rótulo do artigo seguinte, não dispositivo do art. 313 (peculato mediante
    erro de outrem), pedido pela receita `noc-dir-pen-07-crimes-contra`."""
    artigo = extrair_artigo(HTML_CP, "313")

    assert artigo.caput.texto.startswith("Art. 313 - Apropriar-se")
    textos = [
        artigo.caput.texto,
        *(i.texto for i in artigo.incisos),
        *(p.texto for p in artigo.paragrafos),
        *(p.texto for p in artigo.penas),
    ]
    assert not any("Inserção de dados falsos" in t for t in textos)


def test_bloco_sem_pontuacao_no_meio_do_artigo_continua_levantando() -> None:
    """A contraprova da regra (h): a tolerância vale **só** para o último bloco do artigo, onde a
    técnica legislativa põe a rubrica do próximo. No meio do artigo, um bloco sem pontuação de
    fechamento segue sendo `EstruturaNaoTratada` — é o que impede o heurístico de voltar a ser o
    "qualquer texto sem ponto final é título" derrubado na revisão de 19/09/2026."""
    html = (
        "<p>Art. 99. É vedado ao servidor público, sob pena de demissão:</p>"
        "<p>Rubrica Que Parece Titulo Mas Esta No Meio</p>"
        "<p>II - receber vantagem indevida;</p>"
        "<p>Art. 100. Outro artigo qualquer.</p>"
    )

    with pytest.raises(EstruturaNaoTratada, match="Rubrica Que Parece"):
        extrair_artigo(html, "99")
