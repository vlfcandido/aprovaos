# O que é: testes do passo 13 da V3 — rotas HTML de resolver questão (`GET`/`POST
# /topico/{slug}/questoes`) e de reportar erro (`POST /questoes/{id}/reportar`): isolamento por
# tenant no slug (o tópico é vocabulário global), certeza/dúvida obrigatória antes de responder,
# gabarito nunca no HTML antes da resposta, origem completa no resultado e a premissa H (reporte
# esconde a questão só para quem reportou). Quando ler: ao mexer em `api/questoes.py` ou nos
# templates `questoes/*.html`.
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import (
    Concurso,
    Documento,
    Edital,
    EventoEstudo,
    Questao,
    ReporteErro,
    Topico,
    TopicoEdital,
    Usuario,
)
from aprovaos.dados.repositorio_questao import salvar_questoes
from aprovaos.dominio.questao import Origem, QuestaoCurada, RegraProva, hash_dedup

CADASTRO = {"email": "linda@exemplo.com", "senha": "12345678"}
OUTRA_CONTA = {"email": "outra@exemplo.com", "senha": "12345678"}
SLUG = "dir-adm-04-licitacoes-contratos"


@pytest.fixture
def logado(cliente: TestClient) -> TestClient:
    resposta = cliente.post("/cadastro", data=CADASTRO, follow_redirects=False)
    assert resposta.status_code == 303
    return cliente


def _usuario_por_email(db: Session, email: str) -> Usuario:
    return db.scalars(select(Usuario).where(Usuario.email == email)).one()


def _documento(db: Session, hash_: str) -> Documento:
    documento = Documento(
        tipo="prova", hash=hash_, caminho=f"{hash_}.pdf", baixado_em=agora_utc(), metadados={}
    )
    db.add(documento)
    db.flush()
    return documento


def _edital_com_topico(db: Session, tenant_id: UUID, slug: str) -> tuple[Edital, Topico]:
    topico = Topico(materia="DIREITO ADMINISTRATIVO", nome="Licitações e contratos", slug=slug)
    documento_edital = _documento(db, f"edital-{slug}")
    concurso = Concurso(tenant_id=tenant_id, orgao="TJ-PA", cargo="Analista", banca="cebraspe")
    edital = Edital(concurso=concurso, versao=1, documento=documento_edital)
    db.add_all([topico, concurso, edital])
    db.flush()
    db.add(TopicoEdital(edital=edital, topico=topico, ordem=1, texto_original="4. Licitações..."))
    db.flush()
    return edital, topico


TEXTO_APOIO_CURTO = "Texto de apoio compartilhado com outros itens."


def _questao_curada(
    topico_slug: str,
    documento_id: UUID,
    *,
    numero_item: int = 58,
    gabarito: str = "C",
    publicavel: bool = True,
    texto_apoio: str = TEXTO_APOIO_CURTO,
) -> QuestaoCurada:
    origem = Origem(
        banca="cebraspe",
        orgao="TJ-PA",
        cargo="Analista Judiciário — Direito",
        ano=2025,
        numero_item=numero_item,
        tipo_caderno="TIPO 1",
        url_prova="https://cdn.cebraspe.org.br/prova.pdf",
        documento_id=str(documento_id),
    )
    return QuestaoCurada(
        banca="cebraspe",
        numero_item=numero_item,
        comando="Julgue o item a seguir.",
        texto_apoio=texto_apoio,
        texto_apoio_itens=[numero_item],
        enunciado="O pregão eletrônico dispensa a fase de habilitação prévia.",
        gabarito_preliminar=None,
        gabarito=gabarito,
        gabarito_status="definitivo",
        publicavel=publicavel,
        motivo_nao_publicavel=None if publicavel else "tópico não identificado",
        regra_prova=RegraProva(anula_por_erro=True, fonte="instrução do caderno"),
        topico_slug=topico_slug,
        topico_confianca="alta",
        topico_evidencia="menciona pregão e licitação",
        origem=origem,
        hash_dedup=hash_dedup(f"{numero_item}-{gabarito}-{topico_slug}"),
    )


def _criar_questao(db: Session, topico: Topico, documento_id: UUID, **kwargs: Any) -> Questao:
    curada = _questao_curada(topico.slug, documento_id, **kwargs)
    salvar_questoes(db, [curada])
    db.commit()
    return db.scalars(select(Questao).where(Questao.hash_dedup == curada.hash_dedup)).one()


def test_get_topico_exige_login(cliente: TestClient) -> None:
    resposta = cliente.get(f"/topico/{SLUG}/questoes", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_get_topico_de_outro_tenant_404(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-1")
    _criar_questao(db, topico, documento.id)

    logado.cookies.clear()
    resposta_cadastro = logado.post("/cadastro", data=OUTRA_CONTA, follow_redirects=False)
    assert resposta_cadastro.status_code == 303

    resposta = logado.get(f"/topico/{topico.slug}/questoes")
    assert resposta.status_code == 404
    corpo = resposta.json()
    assert corpo["codigo"] == "nao_encontrado"
    assert set(corpo) == {"codigo", "mensagem", "acao"}


def test_get_mostra_questao_com_origem(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-2")
    _criar_questao(db, topico, documento.id)

    resposta = logado.get(f"/topico/{topico.slug}/questoes")
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "Julgue o item a seguir." in corpo
    assert "Texto de apoio compartilhado com outros itens." in corpo
    assert "O pregão eletrônico dispensa a fase de habilitação prévia." in corpo
    assert "TJ-PA" in corpo
    assert "Analista Judiciário — Direito" in corpo
    assert "2025" in corpo
    assert "item 58" in corpo
    assert "TIPO 1" in corpo
    assert 'href="https://cdn.cebraspe.org.br/prova.pdf"' in corpo
    assert "Gabarito" not in corpo


def test_apoio_curto_nao_fica_recolhido(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-2b")
    _criar_questao(db, topico, documento.id, texto_apoio=TEXTO_APOIO_CURTO)

    corpo = logado.get(f"/topico/{topico.slug}/questoes").text
    assert "<details" not in corpo
    assert TEXTO_APOIO_CURTO in corpo


def test_apoio_longo_fica_recolhido(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-2c")
    texto_longo = "Lei nº 14.133/2021, art. 1º. " * 25  # bem mais que 600 caracteres
    assert len(texto_longo) > 600
    _criar_questao(db, topico, documento.id, texto_apoio=texto_longo)

    corpo = logado.get(f"/topico/{topico.slug}/questoes").text
    assert "<details" in corpo
    assert "<summary>ver texto de apoio</summary>" in corpo
    assert texto_longo in corpo


def test_post_resposta_sem_confianca_400(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-3")
    questao = _criar_questao(db, topico, documento.id)

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "C", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 400
    corpo = resposta.json()
    assert corpo["codigo"] == "dados_invalidos"
    assert "certeza ou dúvida" in corpo["mensagem"].lower()
    assert set(corpo) == {"codigo", "mensagem", "acao"}

    eventos = list(db.scalars(select(EventoEstudo)).all())
    assert eventos == []


def test_post_resposta_grava_evento_e_devolve_fragmento(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-4")
    questao = _criar_questao(db, topico, documento.id, gabarito="C")

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "C", "confianca": "certeza", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 200
    assert "Certo" in resposta.text

    eventos = list(db.scalars(select(EventoEstudo).where(EventoEstudo.tipo == "resposta")).all())
    assert len(eventos) == 1
    assert eventos[0].questao_id == questao.id
    assert eventos[0].acertou is True
    assert eventos[0].confianca_declarada == "certeza"


def test_resultado_mostra_origem_completa_e_reportar(logado: TestClient, db: Session) -> None:
    """Decisão 4 do passo 14: a origem aparece no resultado, sempre — e o botão de reportar
    continua disponível ali, já que o fragmento substituiu o resto de `#questao`.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-4b")
    questao = _criar_questao(db, topico, documento.id, gabarito="C")

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "C", "confianca": "certeza", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "cebraspe" in corpo
    assert "TJ-PA" in corpo
    assert "Analista Judiciário — Direito" in corpo
    assert "2025" in corpo
    assert "item 58" in corpo
    assert 'href="https://cdn.cebraspe.org.br/prova.pdf"' in corpo
    assert f'action="/questoes/{questao.id}/reportar"' in corpo


def test_topico_tela_referencia_atalhos_de_teclado(logado: TestClient, db: Session) -> None:
    """Os botões grandes e o link "próxima" carregam os `data-atalho` que a ilha de JS usa
    (ADR-0019); sem o script, eles continuam clicáveis normalmente (decisão 5 do passo 14).
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-4c")
    _criar_questao(db, topico, documento.id)

    corpo = logado.get(f"/topico/{topico.slug}/questoes").text
    assert '<script src="/static/js/atalhos-estudo.js" defer></script>' in corpo
    assert 'data-atalho="certo"' in corpo
    assert 'data-atalho="errado"' in corpo


def test_post_resposta_questao_de_outro_topico_erro(logado: TestClient, db: Session) -> None:
    """`questao_id` de uma questão de outro tópico não pode ser aceito — sem isso, um `id`
    adulterado no formulário gravaria a resposta contra uma questão que a tela nunca mostrou.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    _edital_b, topico_b = _edital_com_topico(db, dona.tenant_id, "dir-adm-05-contratos")
    documento = _documento(db, "prova-6")
    _criar_questao(db, topico, documento.id)
    questao_de_outro_topico = _criar_questao(db, topico_b, documento.id, numero_item=59)

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={
            "resposta": "C",
            "confianca": "certeza",
            "questao_id": str(questao_de_outro_topico.id),
        },
    )
    assert resposta.status_code == 404
    corpo = resposta.json()
    assert set(corpo) == {"codigo", "mensagem", "acao"}

    eventos = list(db.scalars(select(EventoEstudo)).all())
    assert eventos == []


def test_post_resposta_questao_ja_respondida_erro(logado: TestClient, db: Session) -> None:
    """`questao_id` de uma questão que este usuário já respondeu não pode gravar de novo —
    `evento_estudo` é append-only e é matéria-prima do FSRS, um evento errado não tem conserto.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-7")
    questao = _criar_questao(db, topico, documento.id, gabarito="C")

    primeira = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "C", "confianca": "certeza", "questao_id": str(questao.id)},
    )
    assert primeira.status_code == 200

    segunda = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "E", "confianca": "duvida", "questao_id": str(questao.id)},
    )
    assert segunda.status_code == 404
    corpo = segunda.json()
    assert set(corpo) == {"codigo", "mensagem", "acao"}

    eventos = list(db.scalars(select(EventoEstudo).where(EventoEstudo.tipo == "resposta")).all())
    assert len(eventos) == 1
    assert eventos[0].resposta == "C"


def test_post_reporte(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-5")
    questao = _criar_questao(db, topico, documento.id)

    resposta = logado.post(
        f"/questoes/{questao.id}/reportar", data={"motivo": "gabarito parece errado"}
    )
    assert resposta.status_code == 200

    reportes = list(db.scalars(select(ReporteErro)).all())
    assert len(reportes) == 1
    assert reportes[0].status == "aberto"
    assert reportes[0].conteudo_id == questao.id

    seguinte = logado.get(f"/topico/{topico.slug}/questoes")
    assert "Ainda não temos questões deste tópico." in seguinte.text


def test_topico_sem_questao(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital_com_topico(db, dona.tenant_id, SLUG)

    resposta = logado.get(f"/topico/{SLUG}/questoes")
    assert resposta.status_code == 200
    assert "Ainda não temos questões deste tópico." in resposta.text
