# O que é: testes do passo 14 da V2 — `GET /editais` (lista dos concursos do tenant, o último
# marcado como principal) e a entrada "Meus editais" na navegação e em `/conta`. Quando ler: ao
# mexer em `editais/lista.html`, `base.html` ou `conta/conta.html`.
import re
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Assinatura, Concurso, Usuario
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
    # ADR-0015: Free processa o DNA de 1 concurso só — o segundo upload deste teste (ele testa a
    # listagem/"principal" com 2 concursos, não o limite) precisa de um tenant Pro.
    usuario = db.scalars(select(Usuario)).one()
    db.add(
        Assinatura(
            usuario_id=usuario.id,
            tier="pro",
            periodicidade="mensal",
            status="ativa",
            inicio=agora_utc(),
            fim=date(2099, 1, 1),
            gateway="mercado_pago",
            id_externo="teste-pro",
        )
    )
    db.commit()
    segundo = _subir(logado)

    corpo = logado.get("/editais").text
    links = re.findall(r'<a href="(/concurso/[0-9a-f-]{36})"', corpo)
    assert links == [segundo, primeiro]
    assert "ASSESSOR DE GABINETE" in corpo
    assert "CÂMARA MUNICIPAL DE CASCAVEL" in corpo
    # Só o cartão mais recente (`segundo`) leva o selo de principal — entre o link dele e o do
    # próximo cartão (`primeiro`).
    assert corpo.count('chip accent">principal<') == 1
    indice_segundo = corpo.index(f'href="{segundo}"')
    indice_selo = corpo.index('chip accent">principal<')
    indice_primeiro = corpo.index(f'href="{primeiro}"')
    assert indice_segundo < indice_selo < indice_primeiro
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
