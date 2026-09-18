# O que é: testes do passo 4 da V1 — engine e fábrica de sessão só por chamada explícita.
# Quando ler: ao mudar como o backend abre conexão com o banco.
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from aprovaos.dados.conexao import criar_engine, criar_fabrica_sessao


def test_criar_engine_nao_conecta(tmp_path: Path) -> None:
    arquivo = tmp_path / "x.db"
    engine = criar_engine("sqlite:///" + str(arquivo))
    assert isinstance(engine, Engine)
    assert not arquivo.exists()
    engine.dispose()


def test_fabrica_sessao_liga_ao_engine() -> None:
    engine = criar_engine("sqlite://")
    fabrica = criar_fabrica_sessao(engine)
    with fabrica() as db:
        assert isinstance(db, Session)
        assert db.get_bind() is engine
    engine.dispose()
