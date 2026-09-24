# O que é: testes do passo 3 da V4 — `GET/POST /revisar` (revisão espaçada, F4.3): mostra o
# cartão vencido reaproveitando a tela de questão, agenda vazia quando não há nada vencido,
# revisar grava `evento_estudo(tipo="revisao_cartao")` e atualiza o `due`, e o isolamento entre
# usuários (cartão de outra conta nunca aparece nem pode ser respondido). Quando ler: ao mexer em
# `GET/POST /revisar` ou no parcial `questoes/_cartao_questao.html`.
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Cartao, EventoEstudo, Questao, Topico, Usuario
from aprovaos.dados.repositorio_cartao import registrar_erro
from tests.test_rota_questoes import (
    CADASTRO,
    OUTRA_CONTA,
    SLUG,
    _criar_questao,
    _documento,
    _edital_com_topico,
    _usuario_por_email,
)


@pytest.fixture
def logado(cliente: TestClient) -> TestClient:
    # Fixture própria (não importada) — mesma convenção de `test_rota_concurso.py`: importar um
    # nome de fixture usado como parâmetro em vários testes deste módulo dispara F811 no ruff.
    resposta = cliente.post("/cadastro", data=CADASTRO, follow_redirects=False)
    assert resposta.status_code == 303
    return cliente


def _questao_e_cartao_vencido(
    db: Session, usuario: Usuario, topico: Topico, *, hash_documento: str
) -> tuple[Questao, Cartao]:
    documento = _documento(db, hash_documento)
    questao = _criar_questao(db, topico, documento.id, gabarito="C")
    cartao = registrar_erro(db, usuario, questao, "duvida", agora_utc() - timedelta(days=1))
    assert cartao is not None
    db.commit()
    return questao, cartao


def test_get_revisar_exige_login(cliente: TestClient) -> None:
    resposta = cliente.get("/revisar", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_get_revisar_sem_cartao_vencido(logado: TestClient) -> None:
    resposta = logado.get("/revisar")
    assert resposta.status_code == 200
    assert "Nenhum cartão vencido" in resposta.text


def test_get_revisar_mostra_a_questao_do_cartao_vencido(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    questao, cartao = _questao_e_cartao_vencido(db, dona, topico, hash_documento="rev-1")

    resposta = logado.get("/revisar")
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "O pregão eletrônico dispensa a fase de habilitação prévia." in corpo
    assert "Gabarito" not in corpo  # nunca revela antes de responder
    assert 'action="/revisar"' in corpo
    assert f'value="{cartao.id}"' in corpo
    assert f'value="{questao.id}"' in corpo
    assert 'id="questao" aria-live="polite"' in corpo
    assert '<script src="/static/js/confianca-questao.js?v=' in corpo


def test_post_revisar_grava_evento_revisao_e_atualiza_due(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    questao, cartao = _questao_e_cartao_vencido(db, dona, topico, hash_documento="rev-2")
    due_antes = cartao.due

    resposta = logado.post(
        "/revisar",
        data={
            "resposta": "C",
            "confianca": "certeza",
            "questao_id": str(questao.id),
            "cartao_id": str(cartao.id),
        },
    )
    assert resposta.status_code == 200
    assert "Certo" in resposta.text
    assert 'href="/revisar"' in resposta.text

    eventos = list(
        db.scalars(select(EventoEstudo).where(EventoEstudo.tipo == "revisao_cartao")).all()
    )
    assert len(eventos) == 1
    assert eventos[0].cartao_id == cartao.id
    assert eventos[0].questao_id == questao.id
    assert eventos[0].acertou is True

    db.expire_all()  # a escrita foi por outra sessão (a da rota) — sem isto o `cartao` fica stale
    linha = db.get(Cartao, cartao.id)
    assert linha is not None
    assert linha.due != due_antes
    assert linha.due > due_antes  # acertou com certeza — o FSRS empurra a agenda para a frente


def test_post_revisar_sem_confianca_reexibe_o_cartao_com_aviso(
    logado: TestClient, db: Session
) -> None:
    """Mesmo defeito nº 1 do porte visual (fatia 14 §2.1), mesma correção: sem confiança válida,
    200 reexibindo o cartão com o aviso — nunca um 400 que o htmx engoliria em silêncio.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    questao, cartao = _questao_e_cartao_vencido(db, dona, topico, hash_documento="rev-conf")

    resposta = logado.post(
        "/revisar",
        data={"resposta": "C", "questao_id": str(questao.id), "cartao_id": str(cartao.id)},
    )
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "certeza ou dúvida" in corpo.lower()
    assert 'role="alert"' in corpo
    assert f'value="{cartao.id}"' in corpo  # o formulário continua ali, pronto para tentar de novo

    eventos = list(
        db.scalars(select(EventoEstudo).where(EventoEstudo.tipo == "revisao_cartao")).all()
    )
    assert eventos == []


def test_post_revisar_de_cartao_de_outro_usuario_e_recusado(
    logado: TestClient, db: Session
) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    questao, cartao = _questao_e_cartao_vencido(db, dona, topico, hash_documento="rev-3")

    logado.cookies.clear()
    resposta_cadastro = logado.post("/cadastro", data=OUTRA_CONTA, follow_redirects=False)
    assert resposta_cadastro.status_code == 303

    resposta = logado.post(
        "/revisar",
        data={
            "resposta": "C",
            "confianca": "certeza",
            "questao_id": str(questao.id),
            "cartao_id": str(cartao.id),
        },
    )
    assert resposta.status_code == 200
    assert "não está mais disponível" in resposta.text

    eventos = list(
        db.scalars(select(EventoEstudo).where(EventoEstudo.tipo == "revisao_cartao")).all()
    )
    assert eventos == []


def test_get_revisar_de_outro_usuario_nao_ve_cartao_alheio(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    _questao_e_cartao_vencido(db, dona, topico, hash_documento="rev-4")

    logado.cookies.clear()
    resposta_cadastro = logado.post("/cadastro", data=OUTRA_CONTA, follow_redirects=False)
    assert resposta_cadastro.status_code == 303

    resposta = logado.get("/revisar")
    assert resposta.status_code == 200
    assert "Nenhum cartão vencido" in resposta.text


# ADR-0051, "sessão com fim visível": a fila de revisão não dizia quantos cartões faltam, então
# a aluna respondia sem saber se era o último ou o vigésimo. Não saber onde termina é o que
# cansa — foi por isso que ela largou o diagnóstico em 23/09/2026.
def test_revisar_diz_quantos_cartoes_faltam(logado: TestClient, db: Session) -> None:
    """Com dois cartões vencidos, a tela diz que faltam dois.

    Os dois cartões precisam vir de questões **diferentes**: `registrar_erro` é idempotente por
    `(usuario, questao)` e `salvar_questoes` deduplica por `hash_dedup`, então repetir o mesmo
    enunciado devolveria um cartão só. `numero_item` é o que muda o hash.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    for numero, marca in ((11, "rev-fila-1"), (22, "rev-fila-2")):
        documento = _documento(db, marca)
        questao = _criar_questao(db, topico, documento.id, gabarito="C", numero_item=numero)
        assert registrar_erro(db, dona, questao, "duvida", agora_utc() - timedelta(days=1))
    db.commit()

    corpo = logado.get("/revisar").text

    assert "2 cartões" in corpo


def test_revisar_no_singular_quando_falta_um(logado: TestClient, db: Session) -> None:
    """Concordância de número: "1 cartão", nunca "1 cartões"."""
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    _questao_e_cartao_vencido(db, dona, topico, hash_documento="rev-fila-unico")

    corpo = logado.get("/revisar").text

    assert "1 cartão" in corpo
    assert "1 cartões" not in corpo
