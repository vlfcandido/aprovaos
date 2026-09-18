# O que é: testes do passo 12 da V1 — rotas `GET/POST /cadastro` (formulário HTMX, criação de
# conta, cookie de sessão, erros re-renderizados). Quando ler: ao mexer em `api/conta.py`.
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from aprovaos.config import Configuracoes
from aprovaos.dados.modelos import Tenant, Usuario
from aprovaos.main import criar_app

FORM = {"email": "Linda@Exemplo.com", "senha": "12345678"}


def test_get_cadastro(cliente: TestClient) -> None:
    resposta = cliente.get("/cadastro")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/html")
    corpo = resposta.text
    assert "<form" in corpo
    assert 'method="post"' in corpo
    assert 'name="email"' in corpo
    assert 'name="senha"' in corpo
    assert 'type="password"' in corpo
    assert 'autocomplete="new-password"' in corpo
    assert 'hx-post="/cadastro"' in corpo
    assert 'hx-select="#form-cadastro"' in corpo
    assert 'hx-target="#form-cadastro"' in corpo


def test_post_cadastro_cria_e_entra(cliente: TestClient, db: Session) -> None:
    resposta = cliente.post("/cadastro", data=FORM, follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/conta"
    cookie = resposta.headers["set-cookie"]
    assert "sessao=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    usuario = db.scalars(select(Usuario).where(Usuario.email == "linda@exemplo.com")).one()
    tenant = db.get(Tenant, usuario.tenant_id)
    assert tenant is not None
    assert tenant.tipo == "pf"


def test_post_cadastro_htmx(cliente: TestClient) -> None:
    resposta = cliente.post(
        "/cadastro", data=FORM, headers={"HX-Request": "true"}, follow_redirects=False
    )
    assert resposta.status_code == 200
    assert resposta.headers["hx-redirect"] == "/conta"
    assert "sessao=" in resposta.headers["set-cookie"]


def test_post_cadastro_email_repetido(cliente: TestClient) -> None:
    cliente.post("/cadastro", data=FORM, follow_redirects=False)
    cliente.cookies.clear()
    resposta = cliente.post("/cadastro", data=FORM, follow_redirects=False)
    assert resposta.status_code == 200
    assert "Já existe conta com este e-mail" in resposta.text
    assert 'href="/entrar"' in resposta.text
    assert "set-cookie" not in resposta.headers


def test_post_cadastro_senha_curta(cliente: TestClient, db: Session) -> None:
    resposta = cliente.post(
        "/cadastro", data={"email": "linda@exemplo.com", "senha": "1234567"}, follow_redirects=False
    )
    assert resposta.status_code == 200
    assert "no mínimo 8" in resposta.text
    assert "set-cookie" not in resposta.headers
    assert db.scalars(select(Usuario)).first() is None


def test_post_cadastro_email_invalido(cliente: TestClient, db: Session) -> None:
    resposta = cliente.post(
        "/cadastro", data={"email": "sem-arroba", "senha": "12345678"}, follow_redirects=False
    )
    assert resposta.status_code == 200
    assert "E-mail inválido" in resposta.text
    assert db.scalars(select(Usuario)).first() is None


def test_cookie_secure_quando_configurado(config_teste: Configuracoes, engine: Engine) -> None:
    app = criar_app(config_teste.model_copy(update={"cookie_seguro": True}), engine=engine)
    with TestClient(app) as cliente:
        resposta = cliente.post("/cadastro", data=FORM, follow_redirects=False)
    assert resposta.status_code == 303
    assert "Secure" in resposta.headers["set-cookie"]
