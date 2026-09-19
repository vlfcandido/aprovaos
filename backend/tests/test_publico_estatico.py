# O que é: disciplina de tokens do CSS das páginas públicas (fatia 13) e que o estático existe.
# Quando ler: ao mexer em `web/static/css/publico.css` ou em `web/templates/publico/*.html`.
import re
from pathlib import Path

from fastapi.testclient import TestClient

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def test_publico_css_servido(cliente: TestClient) -> None:
    resposta = cliente.get("/static/css/publico.css")
    assert resposta.status_code == 200
    assert resposta.content


def test_publico_css_sem_cor_literal_fora_de_tokens() -> None:
    css = (WEB_DIR / "static" / "css" / "publico.css").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
    assert "rgb(" not in css
    assert "rgba(" not in css
    assert "hsl(" not in css
