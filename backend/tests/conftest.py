# O que é: fixtures compartilhadas dos testes do backend — config de teste, engine SQLite em
# memória, app, cliente HTTP e sessão de banco. Quando ler: antes de escrever teste de rota.
import os
from collections.abc import Iterator

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
    """Pula os testes marcados `postgres` quando `DATABASE_URL_TEST` não está definida."""
    if os.environ.get("DATABASE_URL_TEST"):
        return
    pular = pytest.mark.skip(reason="defina DATABASE_URL_TEST")
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(pular)


@pytest.fixture
def config_teste() -> Configuracoes:
    return Configuracoes(
        database_url="sqlite://",
        chave_secreta=SecretStr("t" * 32),
        ambiente="teste",
        cookie_seguro=False,
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
def cliente(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as cliente:
        yield cliente


@pytest.fixture
def db(app: FastAPI) -> Iterator[Session]:
    with app.state.fabrica_sessao() as sessao:
        yield sessao
