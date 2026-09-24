# O que é: testes do passo 3 da fundação jurídica — `dominio.dossie.montar_dossie`, contra o
# HTML real da Lei 8.429/1992 (`knowledge/fixtures/juridico/lei8429_planalto_compilada.htm`).
# Determinístico: sem rede, sem LLM — só `dominio.legislacao.extrair_artigo`/`localizar_trecho`
# sobre HTML já decodificado. Quando ler: ao mudar o formato do dossiê ou investigar por que um
# dispositivo pedido virou lacuna.
from datetime import date
from pathlib import Path

from aprovaos.dominio.dossie import PedidoDispositivo, montar_dossie
from aprovaos.motor.fontes.planalto import decodificar_html

RAIZ = Path(__file__).resolve().parents[2]
_JURIDICO = RAIZ / "knowledge/fixtures/juridico"

HTML_LEI_8429 = decodificar_html((_JURIDICO / "lei8429_planalto_compilada.htm").read_bytes())
URL_LEI_8429 = "https://www.planalto.gov.br/ccivil_03/leis/l8429.htm"
HOJE = date(2026, 9, 19)


def test_dispositivo_que_o_extrator_le_vira_fonte_com_trecho_literal_e_url() -> None:
    """Art. 1º, § 1º da Lei 8.429/1992 (definição de dolo) resolve — vira `F1` com trecho real."""
    conteudo = montar_dossie(
        topico_slug="dir-adm-06-improbidade-administrativa",
        pedidos=[PedidoDispositivo(norma="lei-8429-1992", artigo="1", paragrafo="1")],
        normas_html={"lei-8429-1992": HTML_LEI_8429},
        normas_url={"lei-8429-1992": URL_LEI_8429},
        hoje=HOJE,
    )

    assert len(conteudo.fontes) == 1
    fonte = conteudo.fontes[0]
    assert fonte.id == "F1"
    assert fonte.norma == "lei-8429-1992"
    assert fonte.artigo == "1"
    assert fonte.paragrafo == "1"
    assert fonte.citacao_canonica == "Lei 8.429/1992 art. 1 § 1º"
    assert fonte.url == URL_LEI_8429
    assert "condutas dolosas" in fonte.trecho
    assert fonte.vigente is True
    assert conteudo.lacunas == []
    assert "[F1]" in conteudo.conteudo
    assert fonte.trecho in conteudo.conteudo


def test_dispositivo_que_o_extrator_nao_trata_vira_lacuna_com_trecho_literal_do_erro() -> None:
    """Art. 17 (o § 6º-A tem, no HTML do Planalto, um parêntese aberto e nunca fechado antes da
    anotação "(Incluído pela Lei nº 14.230, de 2021)") vira lacuna, não invenção: o dispositivo
    fica sem pontuação de fechamento e o extrator recusa aceitá-lo como completo.

    Até 23/09/2026 este teste usava o art. 19 ("Pena: detenção de seis a dez meses e multa.",
    solto entre o caput e o parágrafo único) como exemplo de estrutura não tratada — o preceito
    secundário passou a ser tratado (`dominio.legislacao.ArtigoExtraido.penas`) e o art. 19
    resolve; o exemplo mudou, a regra não: o que o extrator não reconhece vira lacuna declarada,
    nunca trecho inventado."""
    conteudo = montar_dossie(
        topico_slug="dir-adm-06-improbidade-administrativa",
        pedidos=[PedidoDispositivo(norma="lei-8429-1992", artigo="17")],
        normas_html={"lei-8429-1992": HTML_LEI_8429},
        normas_url={"lei-8429-1992": URL_LEI_8429},
        hoje=HOJE,
    )

    assert conteudo.fontes == []
    assert len(conteudo.lacunas) == 1
    lacuna = conteudo.lacunas[0]
    assert lacuna.dispositivo == "Lei 8.429/1992 art. 17"
    assert "§ 6º-A" in lacuna.motivo
    assert "truncado" in lacuna.motivo
    # a lacuna é nomeada no conteúdo, mas nenhum trecho de artigo é inventado no lugar dela:
    assert "Lacunas declaradas" in conteudo.conteudo
    assert "[F1]" not in conteudo.conteudo


def test_preceito_secundario_nao_impede_mais_o_artigo_de_virar_fonte() -> None:
    """Art. 19 da Lei 8.429/1992: o caput (denunciação caluniosa) resolve como fonte mesmo com a
    linha "Pena: detenção de seis a dez meses e multa." no corpo do artigo — a pena é lida como
    pena (`ArtigoExtraido.penas`), e o que vira trecho da fonte continua sendo só o dispositivo
    pedido, sem a pena colada nele."""
    conteudo = montar_dossie(
        topico_slug="dir-adm-06-improbidade-administrativa",
        pedidos=[PedidoDispositivo(norma="lei-8429-1992", artigo="19")],
        normas_html={"lei-8429-1992": HTML_LEI_8429},
        normas_url={"lei-8429-1992": URL_LEI_8429},
        hoje=HOJE,
    )

    assert conteudo.lacunas == []
    assert len(conteudo.fontes) == 1
    assert conteudo.fontes[0].trecho.startswith("Art. 19.")
    assert "Pena:" not in conteudo.fontes[0].trecho


def test_norma_sem_html_disponivel_tambem_vira_lacuna() -> None:
    """Norma pedida sem HTML carregado (`normas_html`) é lacuna, não erro de execução."""
    conteudo = montar_dossie(
        topico_slug="dir-adm-06-improbidade-administrativa",
        pedidos=[PedidoDispositivo(norma="lei-14230-2021", artigo="1")],
        normas_html={},
        normas_url={},
        hoje=HOJE,
    )

    assert conteudo.fontes == []
    assert len(conteudo.lacunas) == 1
    assert "sem HTML" in conteudo.lacunas[0].motivo


def test_log_de_buscas_registra_uma_entrada_por_pedido_inclusive_falhas() -> None:
    """Cada pedido (resolvido ou não) vira uma linha do `log_buscas`, com o resultado real."""
    conteudo = montar_dossie(
        topico_slug="dir-adm-06-improbidade-administrativa",
        pedidos=[
            PedidoDispositivo(norma="lei-8429-1992", artigo="1", paragrafo="1"),
            # art. 17: lacuna real (§ 6º-A com parêntese não fechado no HTML do Planalto) — era o
            # art. 19 até 23/09/2026, que passou a resolver com o tratamento do preceito
            # secundário.
            PedidoDispositivo(norma="lei-8429-1992", artigo="17"),
        ],
        normas_html={"lei-8429-1992": HTML_LEI_8429},
        normas_url={"lei-8429-1992": URL_LEI_8429},
        hoje=HOJE,
    )

    assert len(conteudo.log_buscas) == 2
    assert conteudo.log_buscas[0].n == 1
    assert "aberta" in conteudo.log_buscas[0].resultado
    assert conteudo.log_buscas[1].n == 2
    assert "falhou" in conteudo.log_buscas[1].resultado
    assert all(entrada.data == HOJE for entrada in conteudo.log_buscas)


def test_bibliografia_vazia_por_padrao_nenhuma_doutrina_consultada_nesta_rodada() -> None:
    """Nenhuma doutrina foi consultada nesta rodada (determinística) — bibliografia fica vazia."""
    conteudo = montar_dossie(
        topico_slug="dir-adm-06-improbidade-administrativa",
        pedidos=[PedidoDispositivo(norma="lei-8429-1992", artigo="1", paragrafo="1")],
        normas_html={"lei-8429-1992": HTML_LEI_8429},
        normas_url={"lei-8429-1992": URL_LEI_8429},
        hoje=HOJE,
    )

    assert conteudo.bibliografia == []
