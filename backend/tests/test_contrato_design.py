# O que é: as regras de `docs/08-sistema-de-design.md` que dá para verificar sozinho, sem olho
# humano e sem navegador — vigiam os templates e o HTML renderizado das telas principais.
# Quando ler: ao acrescentar regra ao contrato, ou quando um destes testes reprovar uma tela nova.
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ_WEB = Path(__file__).resolve().parents[2] / "web"
TEMPLATES = sorted((RAIZ_WEB / "templates").rglob("*.html"))

# `_arte.html` é SVG portado do protótipo: `transform-origin` em px é geometria do desenho, não
# espaçamento de layout. O contrato fala de espaçamento.
SVG_PORTADO = {"_arte.html"}

ESTILO_COM_PX = re.compile(r'style="[^"]*?\b\d+px')
ESTATICO_CRU = re.compile(r'(?:href|src)="/static/')
PENDENCIA_NA_TELA = re.compile(r"\(P-\d+\)")


def test_ha_templates_para_verificar() -> None:
    """Guarda contra o teste virar vácuo se os caminhos mudarem."""
    assert len(TEMPLATES) > 20


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_espacamento_nao_e_pixel_escrito_a_mao(template: Path) -> None:
    """Contrato §2: pixel de espaçamento em template significa que falta componente ou token.

    A escala vive em `tokens.css` (`--espaco-*`). Um `gap:6px` solto no meio de uma tela é como o
    ritmo vertical se perde: cada tela ganha o seu, ninguém percebe, e o conjunto fica irregular.
    """
    if template.name in SVG_PORTADO:
        pytest.skip("SVG portado do protótipo: px ali é geometria do desenho, não espaçamento")
    achados = ESTILO_COM_PX.findall(template.read_text(encoding="utf-8"))
    assert not achados, f"{template.name}: use um token --espaco-* em vez de {achados}"


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_estatico_sempre_versionado(template: Path) -> None:
    """Endereço de estático passa por `estatico()`, senão o navegador serve a folha do cache."""
    texto = template.read_text(encoding="utf-8")
    sem_comentarios = re.sub(r"\{#.*?#\}", "", texto, flags=re.DOTALL)
    assert not ESTATICO_CRU.search(sem_comentarios), (
        f"{template.name}: use {{{{ estatico('...') }}}} no lugar de /static/ cru"
    )


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_todo_template_diz_o_que_e_e_quando_ler(template: Path) -> None:
    """Regra 5 do CLAUDE.md: todo arquivo abre com o cabeçalho de duas linhas."""
    primeira = template.read_text(encoding="utf-8").lstrip().splitlines()[0]
    assert primeira.startswith("{#"), f"{template.name}: falta o cabeçalho 'O que é / Quando ler'"


TELAS_DE_ALUNA = ["/", "/radar", "/entrar", "/cadastro"]


@pytest.mark.parametrize("caminho", TELAS_DE_ALUNA)
def test_uma_acao_principal_por_tela(cliente: TestClient, caminho: str) -> None:
    """Contrato §1: um `.btn primary` por tela — o segundo é uma decisão que ninguém tomou."""
    corpo = cliente.get(caminho).text
    assert corpo.count('class="btn primary"') <= 1, f"{caminho}: mais de uma ação principal"


@pytest.mark.parametrize("caminho", TELAS_DE_ALUNA)
def test_pendencia_interna_nunca_aparece_na_tela(cliente: TestClient, caminho: str) -> None:
    """Contrato §6: "(P-39)" não quer dizer nada para a aluna — diga o fato, não o número."""
    assert not PENDENCIA_NA_TELA.search(cliente.get(caminho).text), f"{caminho}: pendência na tela"


@pytest.mark.parametrize("caminho", TELAS_DE_ALUNA)
def test_um_titulo_de_tela(cliente: TestClient, caminho: str) -> None:
    """Uma tela responde uma pergunta: um `<h1>`, nem zero nem dois."""
    assert cliente.get(caminho).text.count("<h1") == 1, f"{caminho}: deve ter exatamente um <h1>"
