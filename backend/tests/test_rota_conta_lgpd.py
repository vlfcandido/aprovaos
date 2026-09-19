# O que é: testes red-first de `GET /conta/exportar` e `POST /conta/excluir` (RF-23, Ruling 48).
# Quando ler: ao mexer no export/exclusão de conta em `api/conta.py`.
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Usuario
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dominio.conta import DadosCadastro

EMAIL = "linda@exemplo.com"


def _entrar(cliente: TestClient, db: Session) -> None:
    criar_conta(db, DadosCadastro(email=EMAIL, senha="12345678"))
    db.commit()
    resposta = cliente.post(
        "/entrar", data={"email": EMAIL, "senha": "12345678"}, follow_redirects=False
    )
    assert resposta.status_code == 303


def test_exportar_sem_login_redireciona(cliente: TestClient) -> None:
    resposta = cliente.get("/conta/exportar", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_exportar_devolve_json_com_a_conta(cliente: TestClient, db: Session) -> None:
    _entrar(cliente, db)
    resposta = cliente.get("/conta/exportar")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("application/json")
    corpo = resposta.json()
    assert corpo["conta"]["email"] == EMAIL


def test_excluir_sem_confirmacao_nao_apaga(cliente: TestClient, db: Session) -> None:
    _entrar(cliente, db)
    resposta = cliente.post("/conta/excluir", data={}, follow_redirects=False)
    assert resposta.status_code == 200
    usuario = db.scalars(select(Usuario)).one()
    assert usuario.excluido_em is None


def test_excluir_com_confirmacao_apaga_e_desloga(cliente: TestClient, db: Session) -> None:
    _entrar(cliente, db)
    resposta = cliente.post("/conta/excluir", data={"confirmar": "sim"}, follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"

    usuario = db.scalars(select(Usuario)).one()
    assert usuario.excluido_em is not None
    assert usuario.email != EMAIL

    resposta = cliente.get("/conta", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"
