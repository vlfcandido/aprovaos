# O que é: testes de integração do fio da memória (V5) contra `GET/POST /topico/{slug}/questoes`
# — a cadência (a cada 3 respostas nativas, a 4ª é um item intercalado), o selo com o motivo na
# tela, `evento_estudo.dados` gravado nos dois casos e a rejeição de um `fio_origem_topico_id` de
# fora do tenant. Quando ler: ao mexer na intercalação, em `_contexto_questao` ou nos parciais
# `_cartao_questao.html`/`_resultado.html`.
from datetime import timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import (
    Concurso,
    Edital,
    EventoEstudo,
    Questao,
    Tenant,
    Topico,
    TopicoEdital,
)
from tests.test_rota_questoes import CADASTRO, _criar_questao, _documento, _usuario_por_email

SLUG_ATUAL = "dir-civ-fio-01"
SLUG_OUTRO = "dir-adm-fio-01"


def _edital_com_dois_topicos(db: Session, tenant_id: UUID) -> tuple[Topico, Topico]:
    """Um edital com dois tópicos: o atual (onde a aluna está estudando) e outro já visto."""
    topico_atual = Topico(materia="DIREITO CIVIL", nome="Prescrição", slug=SLUG_ATUAL)
    topico_outro = Topico(
        materia="Direito Constitucional", nome="Controle de constitucionalidade", slug=SLUG_OUTRO
    )
    documento_edital = _documento(db, "edital-fio")
    concurso = Concurso(tenant_id=tenant_id, orgao="TJ-PA", cargo="Analista", banca="cebraspe")
    edital = Edital(concurso=concurso, versao=1, documento=documento_edital)
    db.add_all([topico_atual, topico_outro, concurso, edital])
    db.flush()
    db.add(TopicoEdital(edital=edital, topico=topico_atual, ordem=1, texto_original="1. X."))
    db.add(TopicoEdital(edital=edital, topico=topico_outro, ordem=2, texto_original="2. Y."))
    db.flush()
    return topico_atual, topico_outro


@pytest.fixture
def logado(cliente: TestClient) -> TestClient:
    resposta = cliente.post("/cadastro", data=CADASTRO, follow_redirects=False)
    assert resposta.status_code == 303
    return cliente


def _responder(cliente: TestClient, slug: str, questao: Questao, **extra: str) -> str:
    assert questao.gabarito is not None
    dados = {
        "resposta": questao.gabarito,
        "confianca": "certeza",
        "questao_id": str(questao.id),
        **extra,
    }
    resposta = cliente.post(f"/topico/{slug}/questoes", data=dados)
    assert resposta.status_code == 200
    return resposta.text


def test_sem_historico_de_outro_topico_nunca_intercala(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    topico_atual, _topico_outro = _edital_com_dois_topicos(db, dona.tenant_id)
    documento = _documento(db, "doc-fio-1")
    questoes = [_criar_questao(db, topico_atual, documento.id, numero_item=i) for i in range(1, 6)]

    # Responde 3 nativas — mesmo assim, sem ninguém "já visto" além do próprio tópico atual, o
    # fio da memória nunca aparece: nenhuma estatística elegível.
    for questao in questoes[:3]:
        corpo = _responder(logado, SLUG_ATUAL, questao)
        assert "Fio da memória" not in corpo

    corpo = logado.get(f"/topico/{SLUG_ATUAL}/questoes").text
    assert "Fio da memória" not in corpo
    assert f'value="{questoes[3].id}"' in corpo  # a 4ª nativa, não um item de outro tópico


def test_a_quarta_posicao_do_bloco_intercala_com_motivo_visivel(
    logado: TestClient, db: Session
) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    topico_atual, topico_outro = _edital_com_dois_topicos(db, dona.tenant_id)
    documento = _documento(db, "doc-fio-2")
    nativas = [_criar_questao(db, topico_atual, documento.id, numero_item=i) for i in range(1, 6)]
    ja_respondida = _criar_questao(db, topico_outro, documento.id, numero_item=10, gabarito="E")
    pendente_intercalada = _criar_questao(
        db, topico_outro, documento.id, numero_item=11, gabarito="C"
    )

    # topico_outro já foi visto: uma resposta errada há 6 dias — grava direto (sem passar pela
    # rota) só para controlar a data com precisão no teste.
    db.add(
        EventoEstudo(
            usuario_id=dona.id,
            ocorrido_em=agora_utc() - timedelta(days=6),
            tipo="resposta",
            questao_id=ja_respondida.id,
            acertou=False,
            resposta="C",
            tempo_ms=100,
            confianca_declarada="certeza",
        )
    )
    db.commit()

    for questao in nativas[:3]:
        _responder(logado, SLUG_ATUAL, questao)

    corpo_get = logado.get(f"/topico/{SLUG_ATUAL}/questoes").text
    assert "Fio da memória" in corpo_get
    assert "Direito Constitucional" in corpo_get
    assert "há 6 dias" in corpo_get
    assert "errou 1 de 1" in corpo_get
    assert f'value="{pendente_intercalada.id}"' in corpo_get
    assert f'name="fio_origem_topico_id" value="{topico_outro.id}"' in corpo_get
    assert 'name="fio_motivo"' in corpo_get
    # A 4ª nativa não aparece nesta posição — o item veio do outro tópico.
    assert f'value="{nativas[3].id}"' not in corpo_get

    motivo = "de Direito Constitucional, que você viu há 6 dias e errou 1 de 1"
    corpo_post = _responder(
        logado,
        SLUG_ATUAL,
        pendente_intercalada,
        fio_origem_topico_id=str(topico_outro.id),
        fio_motivo=motivo,
    )
    assert "Fio da memória" in corpo_post

    eventos = list(
        db.scalars(
            select(EventoEstudo).where(EventoEstudo.questao_id == pendente_intercalada.id)
        ).all()
    )
    assert len(eventos) == 1
    evento = eventos[0]
    assert evento.dados is not None
    assert evento.dados["bloco_topico_id"] == str(topico_atual.id)
    assert evento.dados["fio_origem_topico_id"] == str(topico_outro.id)
    assert evento.dados["fio_motivo"] == motivo

    # Posição 4 (0-indexada) não é múltiplo de 4-1: a próxima volta a ser nativa.
    corpo_depois = logado.get(f"/topico/{SLUG_ATUAL}/questoes").text
    assert "Fio da memória" not in corpo_depois
    assert f'value="{nativas[3].id}"' in corpo_depois


def test_fio_origem_topico_id_de_outro_tenant_e_recusado(logado: TestClient, db: Session) -> None:
    """`fio_origem_topico_id` forjado, apontando para um tópico de outro tenant, nunca é aceito
    — mesma garantia de tenant que `_edital_do_topico_para_tenant` já dá às outras rotas.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital_com_dois_topicos(db, dona.tenant_id)
    documento = _documento(db, "doc-fio-3")

    outro_tenant = Tenant(tipo="pf", nome="Outra conta")
    db.add(outro_tenant)
    db.flush()
    topico_alheio = Topico(materia="X", nome="Y", slug="topico-alheio-fio")
    documento_alheio = _documento(db, "edital-alheio")
    concurso_alheio = Concurso(tenant_id=outro_tenant.id, orgao="X", cargo="Y", banca="cebraspe")
    edital_alheio = Edital(concurso=concurso_alheio, versao=1, documento=documento_alheio)
    db.add_all([topico_alheio, concurso_alheio, edital_alheio])
    db.flush()
    db.add(
        TopicoEdital(edital=edital_alheio, topico=topico_alheio, ordem=1, texto_original="1. Z.")
    )
    db.flush()
    questao_alheia = _criar_questao(db, topico_alheio, documento.id, numero_item=99)
    assert questao_alheia.gabarito is not None

    resposta = logado.post(
        f"/topico/{SLUG_ATUAL}/questoes",
        data={
            "resposta": questao_alheia.gabarito,
            "confianca": "certeza",
            "questao_id": str(questao_alheia.id),
            "fio_origem_topico_id": str(topico_alheio.id),
            "fio_motivo": "forjado",
        },
    )
    assert resposta.status_code == 200
    assert "não está mais disponível" in resposta.text

    eventos = list(
        db.scalars(select(EventoEstudo).where(EventoEstudo.questao_id == questao_alheia.id)).all()
    )
    assert eventos == []
