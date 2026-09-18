# O que é: testes do passo 6 da V1 — a migração 0001_base reproduz exatamente `Base.metadata`.
# Quando ler: ao criar migração nova; se `compare_metadata` não devolver `[]`, falta migração.
from collections.abc import Iterator
from pathlib import Path

import alembic.command
import alembic.config
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, create_engine, inspect

import aprovaos.dados.modelos  # noqa: F401  (registra as tabelas em Base.metadata)
from aprovaos.dados.base import Base

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def cfg_alembic(tmp_path: Path) -> alembic.config.Config:
    cfg = alembic.config.Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path}/m.db")
    return cfg


@pytest.fixture
def engine_migrado(cfg_alembic: alembic.config.Config) -> Iterator[Engine]:
    alembic.command.upgrade(cfg_alembic, "head")
    url = cfg_alembic.get_main_option("sqlalchemy.url")
    assert url is not None
    engine = create_engine(url)
    yield engine
    engine.dispose()


def test_migracao_inicial_bate_com_os_modelos(engine_migrado: Engine) -> None:
    with engine_migrado.connect() as conn:
        contexto = MigrationContext.configure(conn)
        diferencas = compare_metadata(contexto, Base.metadata)
    assert diferencas == []


def test_downgrade_remove_tudo(cfg_alembic: alembic.config.Config, engine_migrado: Engine) -> None:
    alembic.command.downgrade(cfg_alembic, "base")
    tabelas = inspect(engine_migrado).get_table_names()
    assert tabelas in (["alembic_version"], [])
