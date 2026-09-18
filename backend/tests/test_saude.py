# O que é: testes do passo 7 da V1 — `GET /saude` toca o banco e responde no formato do produto.
# Quando ler: ao mudar o healthcheck ou a forma como a app recebe o engine.
from pathlib import Path

from fastapi.testclient import TestClient

from aprovaos.config import Configuracoes
from aprovaos.dados.conexao import criar_engine
from aprovaos.main import criar_app


def test_saude_ok(cliente: TestClient) -> None:
    resposta = cliente.get("/saude")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok", "banco": "ok"}


def test_saude_sem_banco(config_teste: Configuracoes, tmp_path: Path) -> None:
    engine = criar_engine("sqlite:///" + str(tmp_path / "nao" / "existe" / "x.db"))
    app = criar_app(config_teste, engine=engine)
    with TestClient(app) as cliente:
        resposta = cliente.get("/saude")
    assert resposta.status_code == 503
    corpo = resposta.json()
    assert set(corpo) == {"codigo", "mensagem", "acao"}
    assert corpo["codigo"] == "banco_indisponivel"
    assert corpo["mensagem"]
    assert corpo["acao"]
