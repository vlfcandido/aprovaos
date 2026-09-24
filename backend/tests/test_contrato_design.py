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


# ---- shell: tema e modo foco (as duas ilhas que mexem no `<html>` antes da primeira pintura) ----

BASE_HTML = RAIZ_WEB / "templates" / "base.html"
NAVEGACAO_HTML = RAIZ_WEB / "templates" / "_navegacao.html"
TEMA_JS = RAIZ_WEB / "static" / "js" / "tema.js"


def test_ilhas_do_shell_sao_sincronas() -> None:
    """Tema e modo foco valem antes da primeira pintura, senão a página pisca no estado errado.

    São as duas únicas exceções ao `defer`: `tema.js` pintaria a cor errada por um quadro e
    `foco.js` mostraria a navegação para escondê-la em seguida.
    """
    corpo = BASE_HTML.read_text(encoding="utf-8")
    for ilha in ("js/tema.js", "js/foco.js"):
        assert f"estatico('{ilha}') }}}}\"></script>" in corpo, f"{ilha}: deve carregar sem defer"


@pytest.mark.parametrize(
    ("arquivo", "atributo"),
    [
        # Os dois controles do shell moram com a navegação (`_navegacao.html`); a saída do modo
        # foco mora no documento, porque precisa ser a primeira parada do Tab quando a navegação
        # some da tela.
        (NAVEGACAO_HTML, "data-alternar-tema"),
        (NAVEGACAO_HTML, "data-modo-foco"),
        (BASE_HTML, "data-sair-do-foco"),
    ],
    ids=lambda valor: valor if isinstance(valor, str) else valor.name,
)
def test_controle_que_depende_de_js_nasce_escondido(arquivo: Path, atributo: str) -> None:
    """Sem JS o botão não faria nada, e botão que não faz nada é pior que botão ausente."""
    corpo = arquivo.read_text(encoding="utf-8")
    (linha,) = [trecho for trecho in corpo.split("<button") if atributo in trecho]
    assert "hidden" in linha.split(">")[0], f"{atributo}: o botão precisa nascer `hidden`"


def test_alternador_oferece_os_tres_temas_mais_o_do_sistema() -> None:
    """Claro, sépia e escuro são de primeira classe (contrato §7) — e o sépia é o de leitura."""
    corpo = TEMA_JS.read_text(encoding="utf-8")
    assert 'CICLO = ["sistema", "claro", "sepia", "escuro"]' in corpo


def test_a_navegacao_mora_no_proprio_arquivo() -> None:
    """A barra lateral é parcial (`_navegacao.html`), como todo bloco reusável daqui.

    Ela voltar para dentro do `base.html` é o que transformava dois trabalhos independentes —
    uma tela e a navegação — em conflito no mesmo arquivo (23/09/2026).
    """
    assert NAVEGACAO_HTML.exists()
    base = BASE_HTML.read_text(encoding="utf-8")
    assert '{% include "_navegacao.html" %}' in base
    assert '<nav class="lateral"' not in base
