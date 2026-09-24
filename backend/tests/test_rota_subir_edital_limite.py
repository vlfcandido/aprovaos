# Nota (24/09/2026): estes testes usam `cliente_com_billing` porque o limite de tier só
# existe quando há caminho para assinar. Com o billing desligado (o padrão do produto
# hoje), `pode_criar_edital`/`pode_responder` liberam — senão o teto do Free seria parede
# sem porta, que foi o que travou a piloto ao subir o segundo edital.
# O que é: teste do passo 4 do plano `docs/fatias/12-billing.md` — `dominio.assinatura
# .pode_criar_edital` aplicado a `POST /editais/subir` (ADR-0015: Free processa o DNA de 1
# concurso). Quando ler: ao mexer no limite de edital com DNA em `api/editais.py`.
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Concurso
from tests.test_rota_subir_edital import CADASTRO

RAIZ = Path(__file__).resolve().parents[2]
PDF = (RAIZ / "knowledge/fixtures/editais/edital-assessor-gabinete.pdf").read_bytes()


@pytest.fixture
def logado(cliente_com_billing: TestClient) -> TestClient:
    # Fixture própria (não importada) — mesma convenção de `test_rota_concurso.py`: importar um
    # nome de fixture usado como parâmetro dispara F811 no ruff.
    resposta = cliente_com_billing.post("/cadastro", data=CADASTRO, follow_redirects=False)
    assert resposta.status_code == 303
    return cliente_com_billing


def test_segundo_edital_com_dna_no_free_mostra_aviso_sem_processar(
    logado: TestClient, db: Session
) -> None:
    primeira = logado.post(
        "/editais/subir",
        files={"arquivo": ("edital.pdf", PDF, "application/pdf")},
        follow_redirects=False,
    )
    assert primeira.status_code == 303

    segunda = logado.post(
        "/editais/subir",
        files={"arquivo": ("edital.pdf", PDF, "application/pdf")},
        follow_redirects=False,
    )
    assert segunda.status_code == 200
    assert "Assine o Pro" in segunda.text
    assert db.scalar(select(func.count()).select_from(Concurso)) == 1
