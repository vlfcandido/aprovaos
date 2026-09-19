# O que é: testes do passo 6 do plano `docs/fatias/1b-radar-e-conta.md` — login por Google
# (RF-20, Ruling 42): sem configuração, 404 e nenhum botão; com configuração, o fluxo inteiro
# contra um provedor falso (mesmo molde de `_ClienteHttp` da `FonteCebraspe`). Quando ler: ao
# mexer em `api/conta.py::entrar_google`/`entrar_google_callback`/`trocar_codigo_por_perfil`.
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from aprovaos.api.conta import trocar_codigo_por_perfil
from aprovaos.config import Configuracoes
from aprovaos.dados.modelos import Usuario
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dominio.conta import DadosCadastro
from aprovaos.dominio.erros import EmailGoogleNaoVerificado, GoogleOAuthIndisponivel
from aprovaos.main import criar_app

CLIENT_ID = "id-de-teste.apps.googleusercontent.com"
CLIENT_SECRET = "segredo-de-teste"


class _RespostaFalsa:
    """Resposta HTTP falsa: só `status_code`/`json()`, o que o login por Google usa."""

    def __init__(self, status_code: int, corpo: Any = None) -> None:
        self.status_code = status_code
        self._corpo = corpo

    def json(self) -> Any:
        """Devolve o corpo decodificado, como `httpx2.Response.json()`."""
        return self._corpo


class ProvedorGoogleFalso:
    """Dublê do provedor Google: token endpoint + userinfo, nunca toca a rede."""

    def __init__(self, perfil: dict[str, Any] | None, status_token: int = 200) -> None:
        self._perfil = perfil or {}
        self._status_token = status_token
        self.chamadas_post: list[tuple[str, Mapping[str, str]]] = []

    def post(self, url: str, *, data: Mapping[str, str]) -> _RespostaFalsa:
        """Simula o token endpoint: devolve `access_token` fixo se `status_token == 200`."""
        self.chamadas_post.append((url, data))
        if self._status_token >= 400:
            return _RespostaFalsa(self._status_token)
        return _RespostaFalsa(200, corpo={"access_token": "token-falso"})

    def get(self, url: str, *, headers: Mapping[str, str]) -> _RespostaFalsa:
        """Simula o `userinfo`: devolve o perfil cadastrado."""
        return _RespostaFalsa(200, corpo=self._perfil)


@pytest.fixture
def config_google(tmp_path: Path) -> Configuracoes:
    """Config com as duas credenciais do Google presentes (login ativo)."""
    return Configuracoes(
        database_url="sqlite://",
        chave_secreta=SecretStr("t" * 32),
        ambiente="teste",
        cookie_seguro=False,
        uploads_dir=tmp_path / "uploads",
        google_oauth_client_id=CLIENT_ID,
        google_oauth_client_secret=SecretStr(CLIENT_SECRET),
        _env_file=None,
    )


@pytest.fixture
def app_google(config_google: Configuracoes, engine: Engine) -> FastAPI:
    return criar_app(config_google, engine=engine)


@pytest.fixture
def cliente_google(app_google: FastAPI) -> Iterator[TestClient]:
    with TestClient(app_google) as cliente:
        yield cliente


@pytest.fixture
def db_google(app_google: FastAPI) -> Iterator[Session]:
    with app_google.state.fabrica_sessao() as sessao:
        yield sessao


def _state_valido(cliente: TestClient) -> str:
    """Pega um `state` de verdade, assinado pela chave do app — a mesma rota que o produz."""
    resposta = cliente.get("/entrar/google", follow_redirects=False)
    assert resposta.status_code == 302
    query = parse_qs(urlparse(resposta.headers["location"]).query)
    return query["state"][0]


def test_sem_configuracao_entrar_google_e_404(cliente: TestClient) -> None:
    assert cliente.get("/entrar/google", follow_redirects=False).status_code == 404


def test_sem_configuracao_callback_e_404(cliente: TestClient) -> None:
    resposta = cliente.get(
        "/entrar/google/callback", params={"code": "x", "state": "y"}, follow_redirects=False
    )
    assert resposta.status_code == 404


def test_sem_configuracao_botao_nao_aparece(cliente: TestClient) -> None:
    assert 'href="/entrar/google"' not in cliente.get("/entrar").text
    assert 'href="/entrar/google"' not in cliente.get("/cadastro").text


def test_com_configuracao_botao_aparece(cliente_google: TestClient) -> None:
    assert 'href="/entrar/google"' in cliente_google.get("/entrar").text
    assert 'href="/entrar/google"' in cliente_google.get("/cadastro").text


def test_entrar_google_redireciona_para_o_consentimento(cliente_google: TestClient) -> None:
    resposta = cliente_google.get("/entrar/google", follow_redirects=False)
    assert resposta.status_code == 302
    destino = urlparse(resposta.headers["location"])
    assert destino.netloc == "accounts.google.com"
    query = parse_qs(destino.query)
    assert query["client_id"] == [CLIENT_ID]
    assert query["response_type"] == ["code"]
    assert "state" in query
    assert query["redirect_uri"] == [f"{cliente_google.base_url}/entrar/google/callback"]


def test_callback_state_adulterado_e_rejeitado(cliente_google: TestClient) -> None:
    resposta = cliente_google.get(
        "/entrar/google/callback",
        params={"code": "abc", "state": "adulterado.semassinatura"},
        follow_redirects=False,
    )
    assert resposta.status_code == 200
    assert "expirou" in resposta.text.lower()
    assert "sessao" not in resposta.headers.get("set-cookie", "")


def test_callback_sem_code_e_rejeitado(cliente_google: TestClient) -> None:
    state = _state_valido(cliente_google)
    resposta = cliente_google.get(
        "/entrar/google/callback", params={"state": state}, follow_redirects=False
    )
    assert resposta.status_code == 200
    assert "expirou" in resposta.text.lower()


def test_callback_email_nao_verificado_e_rejeitado(
    app_google: FastAPI, cliente_google: TestClient
) -> None:
    state = _state_valido(cliente_google)
    app_google.state.cliente_google_oauth = ProvedorGoogleFalso(
        {"sub": "g-1", "email": "linda@exemplo.com", "email_verified": False}
    )
    resposta = cliente_google.get(
        "/entrar/google/callback",
        params={"code": "abc", "state": state},
        follow_redirects=False,
    )
    assert resposta.status_code == 200
    assert "não deu para entrar" in resposta.text.lower()


def test_callback_provedor_fora_do_ar_e_rejeitado(
    app_google: FastAPI, cliente_google: TestClient
) -> None:
    state = _state_valido(cliente_google)
    app_google.state.cliente_google_oauth = ProvedorGoogleFalso(perfil=None, status_token=503)
    resposta = cliente_google.get(
        "/entrar/google/callback",
        params={"code": "abc", "state": state},
        follow_redirects=False,
    )
    assert resposta.status_code == 200
    assert "não deu para entrar" in resposta.text.lower()


def test_callback_cria_conta_nova_e_entra(
    app_google: FastAPI, cliente_google: TestClient, db_google: Session
) -> None:
    state = _state_valido(cliente_google)
    app_google.state.cliente_google_oauth = ProvedorGoogleFalso(
        {"sub": "g-42", "email": "nova@exemplo.com", "email_verified": True}
    )
    resposta = cliente_google.get(
        "/entrar/google/callback",
        params={"code": "abc", "state": state},
        follow_redirects=False,
    )
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/conta"
    assert "sessao=" in resposta.headers["set-cookie"]

    usuario = db_google.scalars(select(Usuario).where(Usuario.email == "nova@exemplo.com")).one()
    assert usuario.google_sub == "g-42"
    assert usuario.senha_hash is None


def test_callback_liga_conta_existente_em_vez_de_duplicar(
    app_google: FastAPI, cliente_google: TestClient, db_google: Session
) -> None:
    criar_conta(db_google, DadosCadastro(email="linda@exemplo.com", senha="12345678"))
    db_google.commit()

    state = _state_valido(cliente_google)
    app_google.state.cliente_google_oauth = ProvedorGoogleFalso(
        {"sub": "g-99", "email": "linda@exemplo.com", "email_verified": True}
    )
    resposta = cliente_google.get(
        "/entrar/google/callback",
        params={"code": "abc", "state": state},
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    usuarios = db_google.scalars(select(Usuario).where(Usuario.email == "linda@exemplo.com")).all()
    assert len(usuarios) == 1
    assert usuarios[0].google_sub == "g-99"
    assert usuarios[0].senha_hash is not None  # a senha original continua funcionando


def test_conta_so_google_nao_vaza_no_login_por_senha(
    app_google: FastAPI, cliente_google: TestClient, db_google: Session
) -> None:
    state = _state_valido(cliente_google)
    app_google.state.cliente_google_oauth = ProvedorGoogleFalso(
        {"sub": "g-7", "email": "sogoogle@exemplo.com", "email_verified": True}
    )
    cliente_google.get(
        "/entrar/google/callback",
        params={"code": "abc", "state": state},
        follow_redirects=False,
    )
    cliente_google.cookies.clear()

    resposta = cliente_google.post(
        "/entrar",
        data={"email": "sogoogle@exemplo.com", "senha": "qualquer-coisa"},
        follow_redirects=False,
    )
    assert resposta.status_code == 200
    assert "inválidos" in resposta.text.lower()


def test_trocar_codigo_por_perfil_provedor_indisponivel() -> None:
    provedor = ProvedorGoogleFalso(perfil=None, status_token=500)
    with pytest.raises(GoogleOAuthIndisponivel):
        trocar_codigo_por_perfil(provedor, CLIENT_ID, CLIENT_SECRET, "code", "https://x/callback")


def test_trocar_codigo_por_perfil_email_nao_verificado() -> None:
    provedor = ProvedorGoogleFalso({"sub": "g", "email": "a@b.com", "email_verified": False})
    with pytest.raises(EmailGoogleNaoVerificado):
        trocar_codigo_por_perfil(provedor, CLIENT_ID, CLIENT_SECRET, "code", "https://x/callback")


def test_trocar_codigo_por_perfil_feliz() -> None:
    provedor = ProvedorGoogleFalso({"sub": "g-1", "email": "A@B.com", "email_verified": True})
    perfil = trocar_codigo_por_perfil(provedor, CLIENT_ID, CLIENT_SECRET, "code", "https://x/cb")
    assert perfil.sub == "g-1"
    assert perfil.email == "a@b.com"
    url_chamada, dados = provedor.chamadas_post[0]
    assert dados["client_id"] == CLIENT_ID
    assert dados["client_secret"] == CLIENT_SECRET
    assert dados["grant_type"] == "authorization_code"
