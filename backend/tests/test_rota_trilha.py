# O que é: testes de `GET /concurso/{id}/trilha` (fatia 6) — a trilha de estudo do concurso,
# mesmo isolamento por tenant de `/concurso/{id}`. Quando ler: ao mexer na rota ou no template
# `editais/trilha.html`.
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.test_rota_subir_edital import CADASTRO, PDF


def _subir(cliente: TestClient) -> str:
    resposta = cliente.post(
        "/editais/subir",
        files={"arquivo": ("edital.pdf", PDF, "application/pdf")},
        follow_redirects=False,
    )
    assert resposta.status_code == 303
    return str(resposta.headers["location"])


@pytest.fixture
def pagina(cliente: TestClient) -> str:
    assert cliente.post("/cadastro", data=CADASTRO, follow_redirects=False).status_code == 303
    return _subir(cliente)


def test_trilha_sem_login_redireciona(cliente: TestClient, pagina: str) -> None:
    cliente.cookies.clear()
    resposta = cliente.get(f"{pagina}/trilha", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_trilha_inexistente_404_json(cliente: TestClient, pagina: str) -> None:
    resposta = cliente.get(f"/concurso/{uuid4()}/trilha")
    assert resposta.status_code == 404


def test_trilha_de_outro_tenant_403(cliente: TestClient, pagina: str) -> None:
    cliente.cookies.clear()
    outra = {"email": "outra-trilha@exemplo.com", "senha": "12345678"}
    assert cliente.post("/cadastro", data=outra, follow_redirects=False).status_code == 303
    resposta = cliente.get(f"{pagina}/trilha")
    assert resposta.status_code == 403


def test_trilha_lista_topicos_do_edital(cliente: TestClient, pagina: str) -> None:
    resposta = cliente.get(f"{pagina}/trilha")
    assert resposta.status_code == 200
    assert "Trilha de estudo" in resposta.text
    assert "não visto" in resposta.text or "nao_visto" in resposta.text
