# O que é: testes do `estatico()` de `api/templates.py` — a versão no endereço do CSS/JS, para
# que uma correção de estilo chegue ao navegador da aluna sem recarga forçada.
# Quando ler: ao mexer em cache de estático ou no registro de globais do Jinja.
from pathlib import Path

from aprovaos.api.templates import criar_estatico, criar_templates


def _montar_web(raiz: Path, conteudo: str = "body{color:red}") -> Path:
    """Monta uma pasta `web/` mínima (templates + estáticos) para os testes."""
    (raiz / "templates").mkdir(parents=True)
    (raiz / "static" / "css").mkdir(parents=True)
    (raiz / "static" / "css" / "base.css").write_text(conteudo, encoding="utf-8")
    return raiz


def test_estatico_acrescenta_versao_ao_endereco(tmp_path: Path) -> None:
    """O endereço sai com `?v=` para o navegador não servir a folha antiga do cache."""
    estatico = criar_estatico(_montar_web(tmp_path))

    endereco = estatico("css/base.css")

    assert endereco.startswith("/static/css/base.css?v=")
    assert len(endereco.split("?v=")[1]) > 0


def test_versao_muda_quando_o_arquivo_muda(tmp_path: Path) -> None:
    """Editar a folha muda a versão — é isto que faz a correção chegar ao tablet da aluna."""
    web = _montar_web(tmp_path)
    estatico = criar_estatico(web)
    antes = estatico("css/base.css")

    (web / "static" / "css" / "base.css").write_text("body{color:blue}", encoding="utf-8")
    depois = estatico("css/base.css")

    assert antes != depois


def test_versao_e_estavel_sem_mudanca(tmp_path: Path) -> None:
    """Sem edição, a versão não muda — senão o navegador rebaixaria o cache a cada visita."""
    estatico = criar_estatico(_montar_web(tmp_path))

    assert estatico("css/base.css") == estatico("css/base.css")


def test_arquivo_ausente_nao_quebra_a_pagina(tmp_path: Path) -> None:
    """Estático que não existe devolve o endereço sem versão — a página não pode morrer por isso."""
    estatico = criar_estatico(_montar_web(tmp_path))

    assert estatico("css/nao-existe.css") == "/static/css/nao-existe.css"


def test_templates_expoem_estatico_como_global(tmp_path: Path) -> None:
    """`{{ estatico('css/base.css') }}` funciona dentro de qualquer template."""
    templates = criar_templates(_montar_web(tmp_path))

    renderizado = templates.env.from_string("{{ estatico('css/base.css') }}").render()

    assert renderizado.startswith("/static/css/base.css?v=")
