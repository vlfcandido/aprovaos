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
    """Art. 9º (título de Seção em Title Case entre ele e o art. 10) vira lacuna, não invenção."""
    conteudo = montar_dossie(
        topico_slug="dir-adm-06-improbidade-administrativa",
        pedidos=[PedidoDispositivo(norma="lei-8429-1992", artigo="9")],
        normas_html={"lei-8429-1992": HTML_LEI_8429},
        normas_url={"lei-8429-1992": URL_LEI_8429},
        hoje=HOJE,
    )

    assert conteudo.fontes == []
    assert len(conteudo.lacunas) == 1
    lacuna = conteudo.lacunas[0]
    assert lacuna.dispositivo == "Lei 8.429/1992 art. 9"
    assert "Seção II" in lacuna.motivo
    assert "Dos Atos de Improbidade" in lacuna.motivo
    # a lacuna é nomeada no conteúdo, mas nenhum trecho de artigo é inventado no lugar dela:
    assert "Lacunas declaradas" in conteudo.conteudo
    assert "[F1]" not in conteudo.conteudo


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
            PedidoDispositivo(norma="lei-8429-1992", artigo="9"),
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
