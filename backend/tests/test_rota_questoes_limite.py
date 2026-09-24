# Nota (24/09/2026): estes testes usam `cliente_com_billing` porque o limite de tier só
# existe quando há caminho para assinar. Com o billing desligado (o padrão do produto
# hoje), `pode_criar_edital`/`pode_responder` liberam — senão o teto do Free seria parede
# sem porta, que foi o que travou a piloto ao subir o segundo edital.
# O que é: testes do passo 4 do plano `docs/fatias/12-billing.md` — o limite de 20 questões/dia
# do Free é conferido ao montar a próxima questão (`GET /topico/{slug}/questoes`), nunca no meio
# de uma resposta, e nunca em `/revisar` nem `/topico/{slug}/aula` (Ruling 47 — "por construção,
# não existe caminho para limitá-las": as duas rotas nem chamam `dominio.assinatura
# .pode_responder`). Quando ler: ao mexer no aviso de limite da tela de questões.
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import EventoEstudo, Topico, Usuario
from aprovaos.dados.repositorio_cartao import registrar_erro
from aprovaos.dominio.assinatura import LIMITES
from tests.test_rota_questoes import (
    CADASTRO,
    SLUG,
    _criar_questao,
    _documento,
    _edital_com_topico,
    _usuario_por_email,
)

#: `LimitesDoTier.questoes_por_dia` é `int | None` no tipo (Pro não tem teto); no Free de hoje é
#: sempre um `int` (ADR-0015) — o `assert` e a anotação só existem para o mypy, não são uma
#: checagem de negócio (o `assert` sozinho não sobrevive à borda de uma função para o mypy).
_limite_free_ou_none = LIMITES["free"].questoes_por_dia
assert _limite_free_ou_none is not None
LIMITE_FREE: int = _limite_free_ou_none


@pytest.fixture
def logado(cliente_com_billing: TestClient) -> TestClient:
    resposta = cliente_com_billing.post("/cadastro", data=CADASTRO, follow_redirects=False)
    assert resposta.status_code == 303
    return cliente_com_billing


def _responder_n_questoes(db: Session, usuario: Usuario, topico: Topico, n: int) -> None:
    """Grava `n` `evento_estudo(tipo="resposta")` de hoje, cada um contra uma questão distinta."""
    for i in range(n):
        documento = _documento(db, f"limite-{i}")
        questao = _criar_questao(db, topico, documento.id, gabarito="C")
        db.add(
            EventoEstudo(
                usuario_id=usuario.id,
                ocorrido_em=agora_utc(),
                tipo="resposta",
                questao_id=questao.id,
                acertou=True,
                resposta="C",
            )
        )
    db.commit()


def test_free_abaixo_do_limite_mostra_questao_normalmente(logado: TestClient, db: Session) -> None:
    usuario = _usuario_por_email(db, "linda@exemplo.com")
    _edital, topico = _edital_com_topico(db, usuario.tenant_id, SLUG)
    documento = _documento(db, "sobrando")
    _criar_questao(db, topico, documento.id, gabarito="C")
    _responder_n_questoes(db, usuario, topico, LIMITE_FREE - 1)

    resposta = logado.get(f"/topico/{SLUG}/questoes")
    assert resposta.status_code == 200
    assert "20 questões de hoje" not in resposta.text


def test_free_no_limite_mostra_aviso_em_vez_de_erro(logado: TestClient, db: Session) -> None:
    usuario = _usuario_por_email(db, "linda@exemplo.com")
    _edital, topico = _edital_com_topico(db, usuario.tenant_id, SLUG)
    _responder_n_questoes(db, usuario, topico, LIMITE_FREE)

    resposta = logado.get(f"/topico/{SLUG}/questoes")
    assert resposta.status_code == 200
    assert "questões de hoje" in resposta.text
    assert "/assinar" in resposta.text


def test_revisao_de_cartao_vencido_nunca_e_limitada(logado: TestClient, db: Session) -> None:
    usuario = _usuario_por_email(db, "linda@exemplo.com")
    _edital, topico = _edital_com_topico(db, usuario.tenant_id, SLUG)
    _responder_n_questoes(db, usuario, topico, LIMITE_FREE)

    documento = _documento(db, "revisao")
    questao = _criar_questao(db, topico, documento.id, gabarito="C")
    registrar_erro(db, usuario, questao, "certeza", agora_utc() - timedelta(days=1))
    db.commit()

    resposta = logado.get("/revisar")
    assert resposta.status_code == 200
    assert "questões de hoje" not in resposta.text


def test_aula_publicada_nunca_e_limitada(logado: TestClient, db: Session) -> None:
    usuario = _usuario_por_email(db, "linda@exemplo.com")
    _edital, topico = _edital_com_topico(db, usuario.tenant_id, SLUG)
    _responder_n_questoes(db, usuario, topico, LIMITE_FREE)

    resposta = logado.get(f"/topico/{SLUG}/aula")
    assert resposta.status_code == 200
    assert "questões de hoje" not in resposta.text
