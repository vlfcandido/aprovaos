# O que é: teste do passo 4 do plano `docs/fatias/12-billing.md` — o limite de 20 questões/dia do
# Free também vale para `GET /diagnostico` (evita que o diagnóstico vire um jeito de contornar o
# limite de prática do dia), sempre sem erro (Ruling 47). Quando ler: ao mexer no aviso de limite
# do diagnóstico.
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import EventoEstudo, Usuario
from aprovaos.dados.repositorio_questao import salvar_questoes
from aprovaos.dominio.assinatura import LIMITES
from tests.test_rota_diagnostico import CADASTRO, _documento, _edital_com_topicos, _questao

#: `LimitesDoTier.questoes_por_dia` é `int | None` no tipo (Pro não tem teto); no Free de hoje é
#: sempre um `int` (ADR-0015) — o `assert` e a anotação só existem para o mypy, não são uma
#: checagem de negócio (o `assert` sozinho não sobrevive à borda de uma função para o mypy).
_limite_free_ou_none = LIMITES["free"].questoes_por_dia
assert _limite_free_ou_none is not None
LIMITE_FREE: int = _limite_free_ou_none


@pytest.fixture
def logado(cliente: TestClient) -> TestClient:
    # Fixture própria (não importada) — mesma convenção de `test_rota_concurso.py`: importar um
    # nome de fixture usado como parâmetro dispara F811 no ruff.
    resposta = cliente.post("/cadastro", data=CADASTRO, follow_redirects=False)
    assert resposta.status_code == 303
    return cliente


def _tenant_id(db: Session) -> UUID:
    return db.scalars(select(Usuario).where(Usuario.email == CADASTRO["email"])).one().tenant_id


def test_diagnostico_no_limite_do_free_mostra_aviso(logado: TestClient, db: Session) -> None:
    tenant_id = _tenant_id(db)
    usuario = db.scalars(select(Usuario).where(Usuario.email == CADASTRO["email"])).one()
    _edital, com_questao, _sem_questao = _edital_com_topicos(db, tenant_id)
    documento = _documento(db, "diag-limite")
    salvar_questoes(db, [_questao(com_questao, documento.id, 1)])
    db.commit()

    for i in range(LIMITE_FREE):
        db.add(
            EventoEstudo(
                usuario_id=usuario.id,
                ocorrido_em=agora_utc(),
                tipo="resposta",
                acertou=True,
                resposta="C",
                dados={"diagnostico": True} if i == 0 else None,
            )
        )
    db.commit()

    resposta = logado.get("/diagnostico")
    assert resposta.status_code == 200
    assert "questões de hoje" in resposta.text
    assert "/assinar" in resposta.text
