"""Fábrica da aplicação FastAPI do AprovaOS.

O que é: `criar_app(config, engine)` — resolve configurações e engine, guarda em `app.state`,
inclui routers e registra tratadores de erro. Quando ler: ao adicionar router ou recurso que
precise nascer com a app. Subir: `uvicorn aprovaos.main:criar_app --factory`.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine

from aprovaos.api import conta, editais, inicio, questoes, saude
from aprovaos.api.erros import registrar_tratadores
from aprovaos.api.templates import criar_templates
from aprovaos.config import Configuracoes, obter_configuracoes
from aprovaos.dados.conexao import criar_engine, criar_fabrica_sessao


def criar_app(config: Configuracoes | None = None, engine: Engine | None = None) -> FastAPI:
    """Cria a aplicação; nada aqui roda em import.

    Args:
        config: configurações explícitas (testes); `None` lê do ambiente/.env.
        engine: engine explícito (testes, SQLite em memória); `None` cria a partir de
            `config.database_url`.

    Returns:
        A app com `app.state.config`, `app.state.fabrica_sessao`, `app.state.templates` e
        `app.state.uploads_dir` (padrão: `data/uploads` na raiz; a pasta só nasce no primeiro
        upload) preenchidos e `/static` montado a partir de `config.web_dir` (padrão: `web/`).
    """
    config = config or obter_configuracoes()
    engine = engine or criar_engine(config.database_url)
    raiz = Path(__file__).resolve().parents[2]
    web_dir = config.web_dir or raiz / "web"

    app = FastAPI(title="AprovaOS", docs_url=None, redoc_url=None)
    app.state.config = config
    app.state.fabrica_sessao = criar_fabrica_sessao(engine)
    app.state.templates = criar_templates(web_dir)
    app.state.uploads_dir = config.uploads_dir or raiz / "data" / "uploads"

    app.mount("/static", StaticFiles(directory=web_dir / "static"), name="static")
    app.include_router(inicio.router)
    app.include_router(conta.router)
    app.include_router(editais.router)
    app.include_router(questoes.router)
    app.include_router(saude.router)
    registrar_tratadores(app)
    return app
