# O que é: testes do passo 14 da V2 — `GET /editais` (lista dos concursos do tenant, o último
# marcado como principal) e a entrada "Meus editais" na navegação e em `/conta`. Quando ler: ao
# mexer em `editais/lista.html`, `base.html` ou `conta/conta.html`.
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Concurso
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
def logado(cliente: TestClient) -> TestClient:
    assert cliente.post("/cadastro", data=CADASTRO, follow_redirects=False).status_code == 303
    return cliente


def test_editais_sem_login_redireciona(cliente: TestClient) -> None:
    resposta = cliente.get("/editais", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_editais_vazio(logado: TestClient) -> None:
    resposta = logado.get("/editais")
    assert resposta.status_code == 200
    assert "Você ainda não subiu nenhum edital" in resposta.text
    assert 'href="/editais/subir"' in resposta.text
    assert "principal" not in resposta.text


def test_editais_lista_e_marca_principal(logado: TestClient, db: Session) -> None:
    primeiro = _subir(logado)
    concurso = db.scalars(select(Concurso)).one()
    concurso.criado_em = concurso.criado_em.replace(year=2025)
    db.commit()
    segundo = _subir(logado)

    corpo = logado.get("/editais").text
    links = re.findall(r'<a href="(/concurso/[0-9a-f-]{36})"', corpo)
    assert links == [segundo, primeiro]
    assert "ASSESSOR DE GABINETE" in corpo
    assert "CÂMARA MUNICIPAL DE CASCAVEL" in corpo
    itens = re.findall(r"<li[^>]*class=\"concurso[^\"]*\"", corpo)
    assert len(itens) == 2
    assert 'class="concurso concurso--principal"' in itens[0]
    assert "principal" not in itens[1]
    assert corpo.count("principal") >= 1
    assert "o último que você subiu" in corpo


def test_editais_nao_mostra_de_outro_tenant(logado: TestClient) -> None:
    _subir(logado)
    logado.cookies.clear()
    outra = {"email": "outra@exemplo.com", "senha": "12345678"}
    assert logado.post("/cadastro", data=outra, follow_redirects=False).status_code == 303
    corpo = logado.get("/editais").text
    assert "Você ainda não subiu nenhum edital" in corpo
    assert "/concurso/" not in corpo


def test_nav_logado_tem_meus_editais(cliente: TestClient) -> None:
    corpo = cliente.get("/").text
    assert 'href="/editais"' not in corpo
    assert "Meus editais" not in corpo
    assert cliente.post("/cadastro", data=CADASTRO, follow_redirects=False).status_code == 303
    corpo = cliente.get("/").text
    assert 'href="/editais"' in corpo
    assert "Meus editais" in corpo


def test_conta_tem_link_para_editais(logado: TestClient) -> None:
    corpo = logado.get("/conta").text
    assert 'href="/editais"' in corpo
    assert "Meus editais" in corpo
