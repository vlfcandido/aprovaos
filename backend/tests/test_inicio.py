# O que é: testes do passo 8 da V1 — landing `/`, estáticos montados e disciplina de cor por token.
# Quando ler: ao mexer em `base.html`, `inicio.html`, nos CSS de `web/static` ou em `/static`.
import re
from pathlib import Path

from fastapi.testclient import TestClient

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def test_landing(cliente: TestClient) -> None:
    resposta = cliente.get("/")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/html")
    corpo = resposta.text
    assert "AprovaOS" in corpo
    assert 'href="/cadastro"' in corpo
    assert 'href="/entrar"' in corpo
    assert '<html lang="pt-BR"' in corpo
    assert 'name="viewport"' in corpo
    assert "color-scheme" in corpo
    assert 'src="/static/js/htmx.min.js?v=' in corpo


def test_estaticos(cliente: TestClient) -> None:
    for caminho in ("/static/css/tokens.css", "/static/css/base.css", "/static/js/htmx.min.js"):
        resposta = cliente.get(caminho)
        assert resposta.status_code == 200, caminho
        assert resposta.content, caminho


def test_tokens_sem_cor_literal_fora_de_tokens() -> None:
    base_css = (WEB_DIR / "static" / "css" / "base.css").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", base_css)
    assert "rgb(" not in base_css
    assert "rgba(" not in base_css
    assert "hsl(" not in base_css


def test_tokens_cobrem_os_dois_temas() -> None:
    tokens_css = (WEB_DIR / "static" / "css" / "tokens.css").read_text(encoding="utf-8")
    assert "color-scheme: light dark" in tokens_css
    assert "@media (prefers-color-scheme: dark)" in tokens_css
    assert ':root:not([data-theme="claro"])' in tokens_css
    assert ':root[data-theme="escuro"]' in tokens_css
    assert "system-ui" in tokens_css


def test_licenca_do_htmx_registra_versao() -> None:
    licenca = (WEB_DIR / "static" / "js" / "LICENSE-htmx.txt").read_text(encoding="utf-8")
    assert re.search(r"htmx\.org@2\.\d+\.\d+", licenca)
    assert "Zero-Clause BSD" in licenca or "0BSD" in licenca
