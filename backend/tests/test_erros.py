# O que é: testes do passo 7 da V1 — todo erro fora de formulário HTML sai como JSON
# `{codigo, mensagem, acao}`. Quando ler: ao adicionar código de erro ou tratador novo.
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel


def _tres_chaves(corpo: dict[str, str]) -> None:
    assert set(corpo) == {"codigo", "mensagem", "acao"}
    assert all(isinstance(v, str) and v for v in corpo.values())


def test_404_em_json(cliente: TestClient) -> None:
    resposta = cliente.get("/nao-existe")
    assert resposta.status_code == 404
    corpo = resposta.json()
    _tres_chaves(corpo)
    assert corpo["codigo"] == "nao_encontrado"
    assert "Not Found" not in corpo["mensagem"]
    assert "não encontrado" in corpo["mensagem"]


def test_422_em_json(app: FastAPI, cliente: TestClient) -> None:
    class Corpo(BaseModel):
        nome: str

    @app.post("/_teste")
    def _rota(corpo: Corpo) -> dict[str, str]:
        return {"nome": corpo.nome}

    resposta = cliente.post("/_teste", json={})
    assert resposta.status_code == 422
    corpo = resposta.json()
    _tres_chaves(corpo)
    assert corpo["codigo"] == "dados_invalidos"
    assert "nome" in corpo["mensagem"]


def test_500_em_json(app: FastAPI) -> None:
    @app.get("/_estoura")
    def _rota() -> None:
        raise RuntimeError("segredo do traceback")

    with TestClient(app, raise_server_exceptions=False) as cliente:
        resposta = cliente.get("/_estoura")
    assert resposta.status_code == 500
    corpo = resposta.json()
    _tres_chaves(corpo)
    assert corpo["codigo"] == "erro_interno"
    assert "segredo do traceback" not in resposta.text
    assert "Traceback" not in resposta.text
