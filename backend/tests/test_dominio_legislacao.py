# O que é: testes do passo 1 da fundação jurídica — `dominio/legislacao.extrair_artigo`, contra
# os dois HTMLs compilados reais do Planalto (CF/1988 art. 37; Lei 14.133/2021 art. 6º), medidos
# em `knowledge/fixtures/juridico/`. Quando ler: ao mudar o extrator ou ao trocar essas fixtures.
from pathlib import Path

import pytest

from aprovaos.dominio.erros import DispositivoNaoEncontrado
from aprovaos.dominio.legislacao import extrair_artigo, localizar_trecho

RAIZ = Path(__file__).resolve().parents[2]
_JURIDICO = RAIZ / "knowledge/fixtures/juridico"


def _ler(nome: str) -> str:
    """Decodifica um HTML compilado do Planalto como `cp1252` (medido: byte 0x92 no arquivo da
    CF é aspa curva do Windows-1252; ISO-8859-1 o trataria como controle indefinido).
    """
    return (_JURIDICO / nome).read_text(encoding="cp1252", errors="replace")


HTML_CF = _ler("constituicao_planalto_compilada.htm")
HTML_LEI_14133 = _ler("lei14133_planalto_compilada.htm")


def test_caput_do_artigo_37_e_o_vigente_pela_ec19_nao_o_revogado() -> None:
    """O caput vigente (pós-EC 19/1998) é devolvido; o texto pré-EC19 (revogado) não aparece."""
    artigo = extrair_artigo(HTML_CF, "37")

    assert artigo.caput.texto == (
        "Art. 37. A administração pública direta e indireta de qualquer dos Poderes da União, "
        "dos Estados, do Distrito Federal e dos Municípios obedecerá aos princípios de "
        "legalidade, impessoalidade, moralidade, publicidade e eficiência e, também, ao "
        "seguinte:"
    )
    assert artigo.caput.redacao_de == "Redação dada pela Emenda Constitucional nº 19, de 1998"
    # o caput pré-EC19 (revogado) começava assim — não pode aparecer em lugar nenhum do artigo:
    texto_revogado = "administração pública direta, indireta ou fundacional"
    assert texto_revogado not in artigo.caput.texto
    assert all(texto_revogado not in inciso.texto for inciso in artigo.incisos)


def test_artigo_37_tem_22_incisos_e_16_paragrafos() -> None:
    """Contagem medida contra o HTML real (I a XXII; §§ 1º a 16, sem §§ 17/18 nesta coleta)."""
    artigo = extrair_artigo(HTML_CF, "37")

    assert [i.identificador for i in artigo.incisos] == [
        "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI",
        "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX", "XXI", "XXII",
    ]  # fmt: skip
    assert [p.identificador for p in artigo.paragrafos] == [
        "§ 1º", "§ 2º", "§ 3º", "§ 4º", "§ 5º", "§ 6º", "§ 7º", "§ 8º",
        "§ 9º", "§ 10.", "§ 11.", "§ 12.", "§ 13.", "§ 14.", "§ 15.", "§ 16.",
    ]  # fmt: skip


def test_inciso_xi_tem_redacao_da_ec41_nao_a_da_ec19_revogada() -> None:
    """O inciso XI vigente é o da EC 41/2003 — a versão EC 19/1998 dele foi revogada."""
    artigo = extrair_artigo(HTML_CF, "37")
    xi = next(i for i in artigo.incisos if i.identificador == "XI")

    assert xi.redacao_de == "Redação dada pela Emenda Constitucional nº 41, 19.12.2003"
    assert "aplicando-se como limite, nos Municípios, o subsídio do Prefeito" in xi.texto


def test_inciso_xxii_foi_incluido_pela_ec42() -> None:
    """O inciso XXII (administrações tributárias) foi incluído pela EC 42/2003."""
    artigo = extrair_artigo(HTML_CF, "37")
    xxii = next(i for i in artigo.incisos if i.identificador == "XXII")

    assert xxii.redacao_de == "Incluído pela Emenda Constitucional nº 42, de 19.12.2003"
    assert xxii.texto.startswith(
        "XXII - as administrações tributárias da União, dos Estados, do Distrito Federal e dos "
        "Municípios"
    )


def test_inciso_xvi_tem_tres_alineas_cada_uma_com_sua_propria_redacao() -> None:
    """A alínea `b` do inciso XVI é a mudança mais recente medida: EC 138/2025."""
    artigo = extrair_artigo(HTML_CF, "37")
    xvi = next(i for i in artigo.incisos if i.identificador == "XVI")

    alineas = {a.identificador: a for a in xvi.alineas}
    assert set(alineas) == {"a", "b", "c"}
    assert alineas["a"].redacao_de == "Redação dada pela Emenda Constitucional nº 19, de 1998"
    assert alineas["b"].redacao_de == "Redação dada pela Emenda Constitucional nº 138, de 2025"
    assert alineas["b"].texto == ("b) a de um cargo de professor com outro de qualquer natureza;")
    assert alineas["c"].redacao_de == "Redação dada pela Emenda Constitucional nº 34, de 2001"


def test_paragrafo_3_tem_tres_incisos_proprios_incluidos_pela_ec19() -> None:
    """§ 3º tem incisos I a III (participação do usuário), aninhados nele, não no artigo."""
    artigo = extrair_artigo(HTML_CF, "37")
    paragrafo_3 = next(p for p in artigo.paragrafos if p.identificador == "§ 3º")

    assert [i.identificador for i in paragrafo_3.alineas] == ["I", "II", "III"]
    assert all(i.tipo == "inciso" for i in paragrafo_3.alineas)
    assert all(
        (i.redacao_de or "").startswith("Incluído pela Emenda Constitucional nº 19, de 1998")
        for i in paragrafo_3.alineas
    )
    # o inciso II carrega ainda uma nota de "Vide Lei" (LAI), medida à parte da redação:
    inciso_ii = next(i for i in paragrafo_3.alineas if i.identificador == "II")
    assert "Vide Lei nº 12.527, de 2011" in (inciso_ii.redacao_de or "")
    # os 3 incisos do § 3º não duplicam a contagem de incisos do caput (que tem 22, não 25):
    assert len(artigo.incisos) == 22


def test_artigo_6_da_lei_14133_e_o_de_definicoes_gerais() -> None:
    """O art. 6º define 60 termos (I a LX) — não define 'licitação' isoladamente."""
    artigo = extrair_artigo(HTML_LEI_14133, "6")

    assert artigo.caput.texto == "Art. 6º Para os fins desta Lei, consideram-se:"
    assert artigo.caput.redacao_de is None
    assert len(artigo.incisos) == 60
    assert artigo.incisos[0].identificador == "I"
    assert artigo.incisos[-1].identificador == "LX"
    assert artigo.paragrafos == []
    assert not any(
        inciso.texto.lower().startswith("licitação:") or " licitação: " in inciso.texto.lower()
        for inciso in artigo.incisos
    )


def test_inciso_ix_da_lei_14133_define_licitante() -> None:
    """O inciso IX (licitante) é o texto usado pelo relatório da fonte jurídica como F-2."""
    artigo = extrair_artigo(HTML_LEI_14133, "6")
    ix = next(i for i in artigo.incisos if i.identificador == "IX")

    assert ix.texto == (
        "IX - licitante: pessoa física ou jurídica, ou consórcio de pessoas jurídicas, que "
        "participa ou manifesta a intenção de participar de processo licitatório, sendo-lhe "
        "equiparável, para os fins desta Lei, o fornecedor ou o prestador de serviço que, em "
        "atendimento à solicitação da Administração, oferece proposta;"
    )


def test_inciso_xxii_da_lei_14133_nao_arrasta_o_link_vigencia_sem_parenteses() -> None:
    """A cadeia 'Vide Decreto ... / Vigência' vira `redacao_de`, nunca gruda no `texto`."""
    artigo = extrair_artigo(HTML_LEI_14133, "6")
    xxii = next(i for i in artigo.incisos if i.identificador == "XXII")

    assert xxii.texto == (
        "XXII - obras, serviços e fornecimentos de grande vulto: aqueles cujo valor estimado "
        "supera R$ 200.000.000,00 (duzentos milhões de reais);"
    )
    assert "Vide Decreto nº 12.807, de 2025" in (xxii.redacao_de or "")
    assert "Vigência" not in xxii.texto


def test_capitulo_e_secao_entre_artigos_nao_viram_dispositivo() -> None:
    """'CAPÍTULO IV' / 'DOS AGENTES PÚBLICOS', entre os arts. 6º e 7º, não aparecem no art. 6º."""
    artigo = extrair_artigo(HTML_LEI_14133, "6")

    textos = [artigo.caput.texto, *(i.texto for i in artigo.incisos)]
    assert not any("CAPÍTULO" in t or "AGENTES PÚBLICOS" in t for t in textos)


def test_artigo_inexistente_levanta_dispositivo_nao_encontrado() -> None:
    """Um número de artigo que não existe na norma levanta erro, nunca um resultado vazio."""
    with pytest.raises(DispositivoNaoEncontrado):
        extrair_artigo(HTML_CF, "999")


# --- localizar_trecho (passo 2 da fundação jurídica: liga uma ReferenciaLegal ao trecho exato) ---


def test_localizar_trecho_sem_inciso_nem_paragrafo_e_o_caput() -> None:
    """Uma citação só ao artigo (sem inciso/parágrafo) resolve para o caput."""
    artigo = extrair_artigo(HTML_CF, "37")

    trecho = localizar_trecho(artigo)

    assert trecho is artigo.caput


def test_localizar_trecho_por_inciso_do_caput() -> None:
    """Uma citação a um inciso do caput resolve para o inciso, não para o caput."""
    artigo = extrair_artigo(HTML_LEI_14133, "6")

    trecho = localizar_trecho(artigo, inciso="IX")

    assert trecho.identificador == "IX"
    assert trecho.texto.startswith("IX - licitante:")


def test_localizar_trecho_por_paragrafo() -> None:
    """Uma citação a um parágrafo resolve pelo número, sem depender do `º`/`.` do identificador."""
    artigo = extrair_artigo(HTML_CF, "37")

    trecho = localizar_trecho(artigo, paragrafo="3")

    assert trecho.identificador == "§ 3º"


def test_localizar_trecho_por_paragrafo_de_dois_digitos() -> None:
    """`"§ 10."` no identificador (sem `º`) ainda casa com a citação `paragrafo="10"`."""
    artigo = extrair_artigo(HTML_CF, "37")

    trecho = localizar_trecho(artigo, paragrafo="10")

    assert trecho.identificador == "§ 10."


def test_localizar_trecho_por_inciso_dentro_de_paragrafo() -> None:
    """Um inciso citado dentro de um parágrafo específico é achado nas alíneas dele."""
    artigo = extrair_artigo(HTML_CF, "37")

    trecho = localizar_trecho(artigo, paragrafo="3", inciso="II")

    assert trecho.identificador == "II"
    assert "Vide Lei nº 12.527, de 2011" in (trecho.redacao_de or "")


def test_localizar_trecho_paragrafo_inexistente_levanta_dispositivo_nao_encontrado() -> None:
    """Um parágrafo que o artigo não tem levanta erro, nunca devolve o caput por engano."""
    artigo = extrair_artigo(HTML_LEI_14133, "6")  # art. 6º da Lei 14.133 não tem parágrafos

    with pytest.raises(DispositivoNaoEncontrado):
        localizar_trecho(artigo, paragrafo="1")


def test_localizar_trecho_inciso_inexistente_levanta_dispositivo_nao_encontrado() -> None:
    """Um inciso que o artigo não tem levanta erro, nunca devolve o caput por engano."""
    artigo = extrair_artigo(HTML_CF, "37")

    with pytest.raises(DispositivoNaoEncontrado):
        localizar_trecho(artigo, inciso="XCIX")
