# O que é: testes de `GET /topico/{slug}/aula` (fatia 6) — isolamento por tenant (mesma regra
# de `/topico/{slug}/questoes`), aviso quando não há aula, e a aula publicada renderizada sem
# marcador `{{...}}` cru, com o fio da memória e as notas de citação. Quando ler: ao mexer na
# rota ou no template `aula/ver.html`.
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import (
    Aula,
    Concurso,
    Documento,
    DossieTopico,
    Edital,
    Topico,
    TopicoEdital,
    Usuario,
)

CADASTRO = {"email": "linda@exemplo.com", "senha": "12345678"}
OUTRA_CONTA = {"email": "outra@exemplo.com", "senha": "12345678"}
SLUG = "dir-adm-06-improbidade-administrativa"


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
    topico = Topico(materia="DIREITO ADMINISTRATIVO", nome="Improbidade", slug=slug)
    documento_edital = _documento(db, f"edital-{slug}")
    concurso = Concurso(tenant_id=tenant_id, orgao="TJ-PA", cargo="Analista", banca="cebraspe")
    edital = Edital(concurso=concurso, versao=1, documento=documento_edital)
    db.add_all([topico, concurso, edital])
    db.flush()
    db.add(TopicoEdital(edital=edital, topico=topico, ordem=1, texto_original="6. Improbidade..."))
    db.flush()
    return edital, topico


def _dossie(db: Session, topico: Topico) -> DossieTopico:
    dossie = DossieTopico(
        topico_id=topico.id,
        versao=1,
        gerado_em=agora_utc(),
        conteudo="conteúdo",
        fontes=[
            {
                "id": "F1",
                "tipo": "norma",
                "citacao_canonica": "Lei 8.429/1992 art. 1",
                "url": "https://planalto.gov.br/lei-8429",
                "trecho": "Os atos de improbidade administrativa tutelará a probidade.",
                "vigente": True,
            }
        ],
        bibliografia=[],
        log_buscas=[],
    )
    db.add(dossie)
    db.flush()
    return dossie


def _aula(db: Session, topico: Topico, dossie: DossieTopico) -> Aula:
    aula = Aula(
        dossie_id=dossie.id,
        dossie_versao=dossie.versao,
        topico_id=topico.id,
        versao=1,
        texto_denso=("A improbidade administrativa tutela a probidade {{Lei 8.429/1992 art. 1}}."),
        texto_leigo="A lei pune improbidade.",
        audio_url=None,
        citacoes=[
            {
                "canonica": "Lei 8.429/1992 art. 1",
                "fonte": "F1",
                "trecho": "Os atos de improbidade administrativa tutelará a probidade.",
                "frase_da_aula": "A improbidade administrativa tutela a probidade",
            }
        ],
        relacionados=[
            {
                "topico_slug": "outro-topico",
                "onde": "§2",
                "frase": "Isso conversa com o que você viu.",
                "trecho": "trecho relacionado",
            }
        ],
        como_a_banca_cobra=[
            {"origem": "cebraspe 2024 tj-pa item 57", "o_que_testou": "troca de verbo"}
        ],
        lacunas_declaradas=["Lei 8.429/1992 art. 2"],
        mnemonico=None,
        validado_em=agora_utc(),
        publicada=True,
    )
    db.add(aula)
    db.flush()
    return aula


def test_sem_aula_mostra_aviso(logado: TestClient, db: Session) -> None:
    usuario = _usuario_por_email(db, CADASTRO["email"])
    _edital_com_topico(db, usuario.tenant_id, SLUG)
    db.commit()

    resposta = logado.get(f"/topico/{SLUG}/aula")

    assert resposta.status_code == 200
    assert "Ainda não temos aula deste tópico." in resposta.text


def test_aula_publicada_aparece_sem_marcador_cru(logado: TestClient, db: Session) -> None:
    usuario = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, usuario.tenant_id, SLUG)
    dossie = _dossie(db, topico)
    _aula(db, topico, dossie)
    db.commit()

    resposta = logado.get(f"/topico/{SLUG}/aula")

    assert resposta.status_code == 200
    assert "{{" not in resposta.text
    assert "[1]" in resposta.text
    assert "Os atos de improbidade administrativa tutelará a probidade." in resposta.text
    assert "Isso conversa com o que você viu." in resposta.text
    assert "cebraspe 2024 tj-pa item 57" in resposta.text
    assert "Lei 8.429/1992 art. 2" in resposta.text


def test_topico_de_outro_tenant_e_404(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital_com_topico(db, dona.tenant_id, SLUG)
    db.commit()

    logado.cookies.clear()
    resposta_cadastro = logado.post("/cadastro", data=OUTRA_CONTA, follow_redirects=False)
    assert resposta_cadastro.status_code == 303

    resposta = logado.get(f"/topico/{SLUG}/aula")
    assert resposta.status_code == 404
