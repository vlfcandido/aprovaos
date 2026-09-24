# O que é: fixtures compartilhadas dos testes do backend — config de teste, engine SQLite em
# memória, app, cliente HTTP e sessão de banco. Quando ler: antes de escrever teste de rota.
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from aprovaos.config import Configuracoes
from aprovaos.dados.base import Base
from aprovaos.main import criar_app


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Pula `postgres` sem `DATABASE_URL_TEST`, `llm` sem `GOOGLE_API_KEY` e `rede` sem
    `APROVAOS_TESTES_DE_REDE`.
    """
    marcadores = {
        "postgres": ("DATABASE_URL_TEST", "defina DATABASE_URL_TEST"),
        "llm": ("GOOGLE_API_KEY", "defina GOOGLE_API_KEY"),
        "rede": ("APROVAOS_TESTES_DE_REDE", "defina APROVAOS_TESTES_DE_REDE=1"),
    }
    for marcador, (variavel, motivo) in marcadores.items():
        if os.environ.get(variavel):
            continue
        pular = pytest.mark.skip(reason=motivo)
        for item in items:
            if marcador in item.keywords:
                item.add_marker(pular)


@pytest.fixture
def config_com_billing(config_teste: Configuracoes) -> Configuracoes:
    """`config_teste` com o billing LIGADO — os limites de tier só existem quando há caminho
    para assinar. Sem a chave do Mercado Pago, `/assinar` é 404 e o teto do Free seria parede
    sem porta (achado com a piloto em 24/09/2026); por isso `pode_criar_edital`/`pode_responder`
    recebem `billing_ativo`. Teste de limite tem de ligar o billing para o limite existir.
    """
    return config_teste.model_copy(update={"mercado_pago_access_token": SecretStr("teste")})


@pytest.fixture
def config_teste(tmp_path: Path) -> Configuracoes:
    # `google_api_key` fica None de propósito: testes de rota seguem o caminho por regras.
    return Configuracoes(
        database_url="sqlite://",
        chave_secreta=SecretStr("t" * 32),
        ambiente="teste",
        cookie_seguro=False,
        uploads_dir=tmp_path / "uploads",
        _env_file=None,
    )


@pytest.fixture
def engine() -> Iterator[Engine]:
    # `StaticPool` + `check_same_thread=False`: o TestClient roda a app em outra thread e o
    # banco em memória precisa ser a mesma conexão (doc oficial do dialeto SQLite).
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def app(config_teste: Configuracoes, engine: Engine) -> FastAPI:
    return criar_app(config_teste, engine=engine)


@pytest.fixture
def app_com_billing(config_com_billing: Configuracoes, engine: Engine) -> FastAPI:
    """App com o billing ligado — para os testes que precisam dos limites de tier de pé."""
    return criar_app(config_com_billing, engine=engine)


@pytest.fixture
def cliente_com_billing(app_com_billing: FastAPI) -> Iterator[TestClient]:
    """Cliente do `app_com_billing`."""
    with TestClient(app_com_billing) as cliente:
        yield cliente


@pytest.fixture
def cliente(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as cliente:
        yield cliente


@pytest.fixture
def db(app: FastAPI) -> Iterator[Session]:
    with app.state.fabrica_sessao() as sessao:
        yield sessao
