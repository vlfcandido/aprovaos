# O que é: testes do passo 17 da V1 — migração e app contra um Postgres real, só quando
# `DATABASE_URL_TEST` existir (senão são pulados). Quando ler: ao subir o Postgres do Compose.
import os
from pathlib import Path

import alembic.command
import alembic.config
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from aprovaos.config import Configuracoes
from aprovaos.dados.base import Base
from aprovaos.main import criar_app

BACKEND = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.postgres


@pytest.fixture
def url_postgres() -> str:
    # O `conftest` já pula a suíte sem a variável; aqui só a lemos.
    return os.environ["DATABASE_URL_TEST"]


@pytest.fixture
def cfg_alembic(url_postgres: str) -> alembic.config.Config:
    cfg = alembic.config.Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url_postgres)
    return cfg


def test_migracao_no_postgres(cfg_alembic: alembic.config.Config, url_postgres: str) -> None:
    alembic.command.downgrade(cfg_alembic, "base")
    alembic.command.upgrade(cfg_alembic, "head")
    engine = create_engine(url_postgres)
    try:
        with engine.connect() as conn:
            diferencas = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    finally:
        engine.dispose()
    assert diferencas == []


def test_app_no_postgres(
    cfg_alembic: alembic.config.Config, url_postgres: str, config_teste: Configuracoes
) -> None:
    alembic.command.downgrade(cfg_alembic, "base")
    alembic.command.upgrade(cfg_alembic, "head")
    app = criar_app(config_teste.model_copy(update={"database_url": url_postgres}))
    with TestClient(app) as cliente:
        assert cliente.get("/saude").json() == {"status": "ok", "banco": "ok"}
        resposta = cliente.post(
            "/cadastro",
            data={"email": "pg@exemplo.com", "senha": "12345678"},
            follow_redirects=False,
        )
        assert resposta.status_code == 303
        assert cliente.get("/conta").status_code == 200
