# O que é: testes de contrato e de fluxo de `GET/POST /diagnostico` (fatia 7, F2.1) — sem login
# redireciona; sem concurso principal avisa sem quebrar; fluxo completo até uma matéria fechar;
# matéria sem questão nunca aparece como item; "insistir" funciona e respeita o teto de 30.
# Quando ler: ao mexer em `api/diagnostico.py`.
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Concurso, Documento, Edital, Questao, Topico, TopicoEdital
from aprovaos.dados.repositorio_questao import salvar_questoes
from aprovaos.dominio.questao import Origem, QuestaoCurada, RegraProva, hash_dedup

CADASTRO = {"email": "linda@exemplo.com", "senha": "12345678"}


@pytest.fixture
def logado(cliente: TestClient) -> TestClient:
    resposta = cliente.post("/cadastro", data=CADASTRO, follow_redirects=False)
    assert resposta.status_code == 303
    return cliente


def _tenant_id(db: Session) -> UUID:
    from aprovaos.dados.modelos import Usuario

    return db.scalars(select(Usuario).where(Usuario.email == CADASTRO["email"])).one().tenant_id


def _documento(db: Session, hash_: str) -> Documento:
    documento = Documento(
        tipo="prova", hash=hash_, caminho=f"{hash_}.pdf", baixado_em=agora_utc(), metadados={}
    )
    db.add(documento)
    db.flush()
    return documento


def _edital_com_topicos(db: Session, tenant_id: UUID) -> tuple[Edital, Topico, Topico]:
    com_questao = Topico(materia="Direito Administrativo", nome="Poderes", slug="diag-a")
    sem_questao = Topico(materia="Língua Portuguesa", nome="Crase", slug="diag-b")
    documento_edital = _documento(db, "edital-diagnostico")
    concurso = Concurso(tenant_id=tenant_id, orgao="TJ-PR", cargo="Técnico", banca="AOCP")
    edital = Edital(concurso=concurso, versao=1, documento=documento_edital)
    db.add_all([com_questao, sem_questao, concurso, edital])
    db.flush()
    db.add_all(
        [
            TopicoEdital(edital=edital, topico=com_questao, ordem=1, texto_original="1. Poderes."),
            TopicoEdital(edital=edital, topico=sem_questao, ordem=2, texto_original="2. Crase."),
        ]
    )
    db.flush()
    return edital, com_questao, sem_questao


def _questao(topico: Topico, documento_id: UUID, numero: int) -> QuestaoCurada:
    origem = Origem(
        banca="cebraspe",
        orgao="TJ-PR",
        cargo="Técnico",
        ano=2025,
        numero_item=numero,
        tipo_caderno=None,
        url_prova="https://cdn.cebraspe.org.br/prova.pdf",
        documento_id=str(documento_id),
    )
    enunciado = f"Enunciado {numero} sobre {topico.nome}."
    return QuestaoCurada(
        banca="cebraspe",
        numero_item=numero,
        comando="Julgue o item.",
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado=enunciado,
        gabarito_preliminar=None,
        gabarito="C",
        gabarito_status="definitivo",
        publicavel=True,
        motivo_nao_publicavel=None,
        regra_prova=RegraProva(anula_por_erro=True, fonte="instrução do caderno"),
        topico_slug=topico.slug,
        topico_confianca="alta",
        topico_evidencia="evidência",
        origem=origem,
        hash_dedup=hash_dedup(enunciado),
    )


def test_diagnostico_exige_login(cliente: TestClient) -> None:
    resposta = cliente.get("/diagnostico", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_diagnostico_sem_concurso_avisa_sem_quebrar(logado: TestClient) -> None:
    resposta = logado.get("/diagnostico")
    assert resposta.status_code == 200
    assert "concurso principal" in resposta.text.lower()


def test_diagnostico_sem_questao_finaliza_direto_sem_fingir_cobertura(
    logado: TestClient, db: Session
) -> None:
    """Nenhum tópico do edital tem questão publicável: finaliza em 0 itens, sem inventar dado."""
    tenant_id = _tenant_id(db)
    edital, _com_questao, _sem_questao = _edital_com_topicos(db, tenant_id)
    db.commit()

    resposta = logado.get("/diagnostico")
    assert resposta.status_code == 200
    assert "diagnóstico concluído" in resposta.text.lower()
    assert "parei em 0 itens" in resposta.text.lower()
    assert "sem questão suficiente na base" in resposta.text.lower()
    assert "sem questão na base" in resposta.text.lower()


def test_diagnostico_flui_ate_a_materia_fechar(logado: TestClient, db: Session) -> None:
    tenant_id = _tenant_id(db)
    edital, com_questao, _sem_questao = _edital_com_topicos(db, tenant_id)
    documento_prova = _documento(db, "prova-diagnostico")
    salvar_questoes(
        db,
        [_questao(com_questao, documento_prova.id, n) for n in range(1, 6)],
    )
    db.commit()

    # Primeiro item: por que este item aparece, e não revela o gabarito.
    resposta = logado.get("/diagnostico")
    assert resposta.status_code == 200
    assert "por que este item" in resposta.text.lower()
    assert "Item <strong>1</strong>" in resposta.text
    assert "<strong>30</strong>" in resposta.text

    # Responde 3 itens com certeza e acerto: a margem em Direito Administrativo fecha
    # (peso 2*3=6, margem = 50/7 ≈ 7,1 ≤ 8) — e Língua Portuguesa nunca aparece (sem questão).
    from aprovaos.dados.modelos import Usuario
    from aprovaos.dados.repositorio_questao import proxima_questao

    usuario = db.scalars(select(Usuario).where(Usuario.email == CADASTRO["email"])).one()
    for _ in range(3):
        db.expire_all()
        pendente = proxima_questao(db, usuario.id, com_questao.id)
        assert pendente is not None
        resposta = logado.post(
            "/diagnostico",
            data={
                "resposta": "C",
                "questao_id": str(pendente.id),
                "topico_id": str(com_questao.id),
                "confianca": "certeza",
                "tempo_ms": "1000",
            },
        )
        assert resposta.status_code == 200
        assert "gabarito" in resposta.text.lower()

    resultado = logado.get("/diagnostico")
    assert resultado.status_code == 200
    assert "diagnóstico concluído" in resultado.text.lower()
    assert "Língua Portuguesa" in resultado.text
    assert "sem questão na base" in resultado.text
    assert "Insistir" in resultado.text  # Direito Administrativo fechou


def test_post_diagnostico_sem_confianca_400(logado: TestClient, db: Session) -> None:
    tenant_id = _tenant_id(db)
    edital, com_questao, _ = _edital_com_topicos(db, tenant_id)
    documento_prova = _documento(db, "prova-2")
    salvar_questoes(db, [_questao(com_questao, documento_prova.id, 1)])
    db.commit()
    questao = db.scalars(select(Questao)).first()
    assert questao is not None

    resposta = logado.post(
        "/diagnostico",
        data={
            "resposta": "C",
            "questao_id": str(questao.id),
            "topico_id": str(com_questao.id),
            "tempo_ms": "500",
        },
    )
    assert resposta.status_code == 400
    corpo = resposta.json()
    assert corpo["codigo"] == "dados_invalidos"
    assert set(corpo) == {"codigo", "mensagem", "acao"}


def test_post_diagnostico_topico_fora_do_edital_404(logado: TestClient, db: Session) -> None:
    tenant_id = _tenant_id(db)
    _edital, com_questao, _ = _edital_com_topicos(db, tenant_id)
    db.commit()
    from uuid import uuid4

    resposta = logado.post(
        "/diagnostico",
        data={
            "resposta": "C",
            "questao_id": str(uuid4()),
            "topico_id": str(uuid4()),
            "confianca": "certeza",
        },
    )
    assert resposta.status_code == 404
    corpo = resposta.json()
    assert corpo["codigo"] == "nao_encontrado"
