# O que é: testes de `motor.fontes.sumulas_offline.resolver_sumulas_offline` — a ponte de I/O
# (páginas do STF, PDF do STJ, ambos em `knowledge/fixtures/juridico/`) entre `PedidoSumula` e os
# dicts `sumulas_texto`/`sumulas_url` que `dominio.dossie.montar_dossie` consome. Quando ler: ao
# acrescentar uma súmula do STF nova (`_PAGINAS_STF_OFFLINE`), ou ao investigar por que uma
# súmula pedida virou lacuna no dossiê.
from aprovaos.dominio.dossie import PedidoSumula
from aprovaos.motor.fontes.sumulas_offline import resolver_sumulas_offline


def test_resolve_sumula_stj_pelo_pdf_unico() -> None:
    pedido = PedidoSumula(chave="stj-sumula-98", tribunal="stj", numero=98)

    texto, url = resolver_sumulas_offline([pedido])

    assert texto["stj-sumula-98"] == (
        "Embargos de declaração manifestados com notório propósito de prequestionamento não "
        "tem caráter protelatório."
    )
    assert url["stj-sumula-98"].endswith("VerbetesSTJ.pdf")


def test_resolve_varias_sumulas_stj_do_mesmo_pdf() -> None:
    pedidos = [
        PedidoSumula(chave="stj-sumula-651", tribunal="stj", numero=651),
        PedidoSumula(chave="stj-sumula-634", tribunal="stj", numero=634),
    ]

    texto, _url = resolver_sumulas_offline(pedidos)

    assert texto["stj-sumula-651"].startswith("Compete à autoridade administrativa aplicar")
    assert texto["stj-sumula-634"].startswith("Ao particular aplica-se")


def test_sumula_stj_inexistente_nao_aparece_no_resultado() -> None:
    """Número que não existe (ou está cancelado) no PDF simplesmente não entra — vira lacuna
    em `montar_dossie`, não erro aqui."""
    pedido = PedidoSumula(chave="stj-sumula-418", tribunal="stj", numero=418)  # cancelada

    texto, _url = resolver_sumulas_offline([pedido])

    assert "stj-sumula-418" not in texto


def test_resolve_sumula_vinculante_stf_pela_pagina_ja_baixada() -> None:
    pedido = PedidoSumula(chave="stf-sv-11", tribunal="stf", numero=11, vinculante=True)

    texto, url = resolver_sumulas_offline([pedido])

    assert texto["stf-sv-11"].startswith("Só é lícito o uso de algemas")
    assert url["stf-sv-11"] == (
        "https://portal.stf.jus.br/jurisprudencia/sumariosumulas.asp?base=26&sumula=1220"
    )


def test_resolve_sumula_comum_stf_pela_pagina_ja_baixada() -> None:
    pedido = PedidoSumula(chave="stf-sumula-473", tribunal="stf", numero=473)

    texto, url = resolver_sumulas_offline([pedido])

    assert texto["stf-sumula-473"].startswith("A administração pode anular")


def test_sumula_stf_sem_pagina_baixada_nesta_rodada_nao_aparece_no_resultado() -> None:
    """Uma súmula do STF sem fixture baixada ainda (`_PAGINAS_STF_OFFLINE` não tem a chave)
    também vira lacuna em `montar_dossie`, não erro aqui — mesma disciplina de
    `motor.ancorar.html_offline_da_norma` para normas sem fixture."""
    pedido = PedidoSumula(chave="stf-sumula-999999", tribunal="stf", numero=999_999)

    texto, url = resolver_sumulas_offline([pedido])

    assert "stf-sumula-999999" not in texto
    assert "stf-sumula-999999" not in url


def test_lista_vazia_devolve_dicts_vazios() -> None:
    texto, url = resolver_sumulas_offline([])

    assert texto == {}
    assert url == {}
