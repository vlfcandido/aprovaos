# O que é: testes do passo 14 da V1 — `GET /conta` protegida, `POST /sair` (revoga sessão e limpa
# cookie) e navegação com estado de login. Quando ler: ao mexer em `api/conta.py` ou `base.html`.
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.api.sessao import NOME_COOKIE
from aprovaos.dados.modelos import Sessao
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dominio.conta import DadosCadastro

EMAIL = "linda@exemplo.com"
LOGIN = {"email": EMAIL, "senha": "12345678"}


def _entrar(cliente: TestClient, db: Session) -> None:
    criar_conta(db, DadosCadastro(email=EMAIL, senha="12345678"))
    db.commit()
    resposta = cliente.post("/entrar", data=LOGIN, follow_redirects=False)
    assert resposta.status_code == 303


def test_conta_sem_login_redireciona(cliente: TestClient) -> None:
    resposta = cliente.get("/conta", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_conta_logado(cliente: TestClient, db: Session) -> None:
    _entrar(cliente, db)
    resposta = cliente.get("/conta")
    assert resposta.status_code == 200
    corpo = resposta.text
    assert EMAIL in corpo
    assert '<form method="post" action="/sair"' in corpo
    assert "Sair" in corpo


def test_sair_revoga_e_limpa(cliente: TestClient, db: Session) -> None:
    _entrar(cliente, db)
    cookie_antigo = cliente.cookies[NOME_COOKIE]
    resposta = cliente.post("/sair", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"
    assert "Max-Age=0" in resposta.headers["set-cookie"]
    linha = db.scalars(select(Sessao)).one()
    assert linha.revogada_em is not None
    cliente.cookies.set(NOME_COOKIE, cookie_antigo)
    resposta = cliente.get("/conta", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_sair_htmx_e_sem_login(cliente: TestClient) -> None:
    resposta = cliente.post("/sair", headers={"HX-Request": "true"}, follow_redirects=False)
    assert resposta.status_code == 200
    assert resposta.headers["hx-redirect"] == "/"
    assert "Max-Age=0" in resposta.headers["set-cookie"]


def test_nav_reflete_login(cliente: TestClient, db: Session) -> None:
    corpo = cliente.get("/").text
    assert "Entrar" in corpo
    assert "Criar conta" in corpo
    assert "Minha conta" not in corpo
    _entrar(cliente, db)
    corpo = cliente.get("/").text
    assert "Minha conta" in corpo
    assert "Criar conta" not in corpo
    assert "Sair" in corpo


def test_cookie_adulterado_e_ignorado(cliente: TestClient) -> None:
    cliente.cookies.set(NOME_COOKIE, "abc.def")
    resposta = cliente.get("/conta", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"
