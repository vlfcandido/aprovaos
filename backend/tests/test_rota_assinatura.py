# O que é: testes do passo 3 do plano `docs/fatias/12-billing.md` — `GET/POST /assinar`,
# `POST /webhooks/pagamento` e `POST /assinatura/cancelar` (Rulings 46-48). Sem
# `MERCADO_PAGO_ACCESS_TOKEN`/`_WEBHOOK_SECRET`, tudo isso é 404 (Ruling 46). Com as duas, o
# fluxo inteiro roda contra `GatewayPagamentoFalso` (`tests/dubles_pagamento.py`). Quando ler: ao
# mexer em `api/assinatura.py`.
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from aprovaos.config import Configuracoes
from aprovaos.dados.modelos import EventoCobranca, Usuario
from aprovaos.dados.repositorio_assinatura import assinatura_do_usuario
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dominio.conta import DadosCadastro
from aprovaos.main import criar_app

from .dubles_pagamento import (
    ASSINATURA_HEADER_VALIDA,
    GatewayPagamentoFalso,
    webhook_assinado_falso,
)

EMAIL = "linda@exemplo.com"
SENHA = "12345678"


@pytest.fixture
def config_billing(tmp_path: Path) -> Configuracoes:
    return Configuracoes(
        database_url="sqlite://",
        chave_secreta=SecretStr("t" * 32),
        ambiente="teste",
        cookie_seguro=False,
        uploads_dir=tmp_path / "uploads",
        mercado_pago_access_token=SecretStr("token-de-teste"),
        mercado_pago_webhook_secret=SecretStr("segredo-de-teste"),
        _env_file=None,
    )


@pytest.fixture
def app_billing(config_billing: Configuracoes, engine: Engine) -> FastAPI:
    app = criar_app(config_billing, engine=engine)
    app.state.gateway_pagamento = GatewayPagamentoFalso()
    return app


@pytest.fixture
def cliente_billing(app_billing: FastAPI) -> Iterator[TestClient]:
    with TestClient(app_billing) as cliente:
        yield cliente


@pytest.fixture
def db_billing(app_billing: FastAPI) -> Iterator[Session]:
    with app_billing.state.fabrica_sessao() as sessao:
        yield sessao


def _entrar(cliente: TestClient, db: Session) -> None:
    criar_conta(db, DadosCadastro(email=EMAIL, senha=SENHA))
    db.commit()
    resposta = cliente.post(
        "/entrar", data={"email": EMAIL, "senha": SENHA}, follow_redirects=False
    )
    assert resposta.status_code == 303


# --- Ruling 46: desligado por padrão -----------------------------------------------------------


def test_sem_configuracao_assinar_e_404(cliente: TestClient) -> None:
    assert cliente.get("/assinar", follow_redirects=False).status_code == 404
    assert (
        cliente.post(
            "/assinar", data={"periodicidade": "mensal"}, follow_redirects=False
        ).status_code
        == 404
    )


def test_sem_configuracao_webhook_e_404(cliente: TestClient) -> None:
    resposta = cliente.post(
        "/webhooks/pagamento",
        content=b"{}",
        headers={"x-signature": "x", "x-request-id": "y"},
        follow_redirects=False,
    )
    assert resposta.status_code == 404


def test_sem_configuracao_cancelar_e_404(cliente: TestClient, db: Session) -> None:
    _entrar(cliente, db)
    assert cliente.post("/assinatura/cancelar", follow_redirects=False).status_code == 404


def test_sem_configuracao_conta_nao_mostra_billing(cliente: TestClient, db: Session) -> None:
    _entrar(cliente, db)
    assert "/assinar" not in cliente.get("/conta").text


# --- com gateway configurado ---------------------------------------------------------------------


def test_assinar_sem_login_redireciona_para_entrar(cliente_billing: TestClient) -> None:
    resposta = cliente_billing.get("/assinar", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_tela_assinar_mostra_os_dois_precos(
    cliente_billing: TestClient, db_billing: Session
) -> None:
    _entrar(cliente_billing, db_billing)
    resposta = cliente_billing.get("/assinar")
    assert resposta.status_code == 200
    assert "59" in resposta.text
    assert "490" in resposta.text


def test_post_assinar_cria_pendente_e_redireciona_para_checkout(
    app_billing: FastAPI, cliente_billing: TestClient, db_billing: Session
) -> None:
    _entrar(cliente_billing, db_billing)
    resposta = cliente_billing.post(
        "/assinar", data={"periodicidade": "mensal"}, follow_redirects=False
    )
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "https://pagamento.falso.exemplo/falso-1"

    usuario = db_billing.scalars(select(Usuario).where(Usuario.email == EMAIL)).one()
    assinatura = assinatura_do_usuario(db_billing, usuario.id)
    assert assinatura is not None
    assert assinatura.id_externo == "falso-1"
    assert assinatura.status == "expirada"  # ainda não confirmada pelo webhook


def test_post_assinar_periodicidade_invalida_e_400(
    cliente_billing: TestClient, db_billing: Session
) -> None:
    _entrar(cliente_billing, db_billing)
    resposta = cliente_billing.post(
        "/assinar", data={"periodicidade": "semanal"}, follow_redirects=False
    )
    assert resposta.status_code == 400


def test_webhook_autorizado_vira_pro(
    app_billing: FastAPI, cliente_billing: TestClient, db_billing: Session
) -> None:
    _entrar(cliente_billing, db_billing)
    cliente_billing.post("/assinar", data={"periodicidade": "mensal"}, follow_redirects=False)

    resposta = cliente_billing.post(
        "/webhooks/pagamento",
        content=webhook_assinado_falso("assinatura_autorizada", "falso-1"),
        headers={"x-signature": ASSINATURA_HEADER_VALIDA, "x-request-id": "req-1"},
    )
    assert resposta.status_code == 200

    usuario_email_resp = cliente_billing.get("/conta").text
    assert "Pro" in usuario_email_resp


def test_webhook_com_assinatura_invalida_e_400_e_nao_grava_nada(
    cliente_billing: TestClient, db_billing: Session
) -> None:
    resposta = cliente_billing.post(
        "/webhooks/pagamento",
        content=webhook_assinado_falso("assinatura_autorizada", "falso-1"),
        headers={"x-signature": "assinatura-errada", "x-request-id": "req-1"},
    )
    assert resposta.status_code == 400
    assert db_billing.scalar(select(EventoCobranca.id)) is None


def test_cancelar_mantem_pro_ate_o_fim_do_periodo(
    app_billing: FastAPI, cliente_billing: TestClient, db_billing: Session
) -> None:
    _entrar(cliente_billing, db_billing)
    cliente_billing.post("/assinar", data={"periodicidade": "mensal"}, follow_redirects=False)
    cliente_billing.post(
        "/webhooks/pagamento",
        content=webhook_assinado_falso("assinatura_autorizada", "falso-1"),
        headers={"x-signature": ASSINATURA_HEADER_VALIDA, "x-request-id": "req-1"},
    )

    resposta = cliente_billing.post("/assinatura/cancelar", follow_redirects=False)
    assert resposta.status_code in (200, 303)

    gateway: GatewayPagamentoFalso = app_billing.state.gateway_pagamento
    assert gateway.canceladas == ["falso-1"]

    texto_conta = cliente_billing.get("/conta").text
    assert "Pro" in texto_conta  # ainda vale até o fim do período


def test_cancelar_sem_assinatura_nao_quebra(
    cliente_billing: TestClient, db_billing: Session
) -> None:
    _entrar(cliente_billing, db_billing)
    resposta = cliente_billing.post("/assinatura/cancelar", follow_redirects=False)
    assert resposta.status_code in (200, 303, 404)
