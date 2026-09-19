# O que é: testes de `GET /concurso/{id}/trilha` (fatia 6) — a trilha de estudo do concurso,
# mesmo isolamento por tenant de `/concurso/{id}`; inclui a correção de 19/09/2026 (I2) que faz
# a trilha atravessar `topico_relacao` (equivalência plena e cobertura parcial) para achar a
# aula, em vez de consultar `Aula` só pelo `topico_id` direto. Quando ler: ao mexer na rota ou no
# template `editais/trilha.html`.
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Concurso, Documento, DossieTopico, Edital, Topico, TopicoEdital
from aprovaos.dados.repositorio_aula import salvar_aula
from aprovaos.dados.repositorio_topico_relacao import (
    criar_relacao_equivalente,
    criar_relacao_subconjunto,
)
from aprovaos.dominio.aula import ConteudoAula
from tests.test_rota_subir_edital import CADASTRO, PDF


def _subir(cliente: TestClient) -> str:
    resposta = cliente.post(
        "/editais/subir",
        files={"arquivo": ("edital.pdf", PDF, "application/pdf")},
        follow_redirects=False,
    )
    assert resposta.status_code == 303
    return str(resposta.headers["location"])


@pytest.fixture
def pagina(cliente: TestClient) -> str:
    assert cliente.post("/cadastro", data=CADASTRO, follow_redirects=False).status_code == 303
    return _subir(cliente)


def test_trilha_sem_login_redireciona(cliente: TestClient, pagina: str) -> None:
    cliente.cookies.clear()
    resposta = cliente.get(f"{pagina}/trilha", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_trilha_inexistente_404_json(cliente: TestClient, pagina: str) -> None:
    resposta = cliente.get(f"/concurso/{uuid4()}/trilha")
    assert resposta.status_code == 404


def test_trilha_de_outro_tenant_403(cliente: TestClient, pagina: str) -> None:
    cliente.cookies.clear()
    outra = {"email": "outra-trilha@exemplo.com", "senha": "12345678"}
    assert cliente.post("/cadastro", data=outra, follow_redirects=False).status_code == 303
    resposta = cliente.get(f"{pagina}/trilha")
    assert resposta.status_code == 403


def test_trilha_lista_topicos_do_edital(cliente: TestClient, pagina: str) -> None:
    resposta = cliente.get(f"{pagina}/trilha")
    assert resposta.status_code == 200
    assert "Trilha de estudo" in resposta.text
    assert "não visto" in resposta.text or "nao_visto" in resposta.text


# --- I2: a trilha atravessa `topico_relacao` para achar a aula, não só o `topico_id` direto ----


def _tenant_id(db: Session, email: str) -> UUID:
    from aprovaos.dados.modelos import Usuario

    return db.scalars(select(Usuario).where(Usuario.email == email)).one().tenant_id


def _documento(db: Session, hash_: str) -> Documento:
    documento = Documento(
        tipo="edital", hash=hash_, caminho=f"{hash_}.pdf", baixado_em=agora_utc(), metadados={}
    )
    db.add(documento)
    db.flush()
    return documento


def _edital_com_topico_alvo(db: Session, tenant_id: UUID, slug_alvo: str) -> tuple[Edital, Topico]:
    """Um edital com um único tópico (`slug_alvo`), sem aula própria — o caso que a trilha
    precisa resolver por relação com outro edital."""
    alvo = Topico(materia="Direito Processual Civil", nome="Dos recursos", slug=slug_alvo)
    documento = _documento(db, f"edital-{slug_alvo}")
    concurso = Concurso(tenant_id=tenant_id, orgao="TJ-PR", cargo="Técnico", banca="AOCP")
    edital = Edital(concurso=concurso, versao=1, documento=documento)
    db.add_all([alvo, concurso, edital])
    db.flush()
    db.add(TopicoEdital(edital=edital, topico=alvo, ordem=1, texto_original="7. Dos recursos."))
    db.flush()
    return edital, alvo


def _topico_com_aula(db: Session, slug: str) -> Topico:
    """Um tópico de outro edital, com dossiê e aula publicada — a fonte que a relação liga."""
    topico = Topico(materia="Direito Processual Civil", nome="Recursos", slug=slug)
    db.add(topico)
    db.flush()
    dossie = DossieTopico(
        topico_id=topico.id,
        versao=1,
        gerado_em=agora_utc(),
        conteudo="conteúdo do dossiê",
        fontes=[{"id": "F1", "tipo": "norma", "citacao_canonica": "CPC art. 1009"}],
        bibliografia=[],
        log_buscas=[],
    )
    db.add(dossie)
    db.flush()
    conteudo = ConteudoAula(
        texto_denso="A apelação é o recurso cabível {{CPC art. 1009}}.",
        texto_leigo="A apelação é o recurso.",
        citacoes=[],
        relacionados=[],
        como_a_banca_cobra=[],
        lacunas_declaradas=[],
    )
    salvar_aula(db, topico_id=topico.id, dossie=dossie, conteudo=conteudo)
    db.flush()
    return topico


def test_trilha_mostra_aula_de_topico_equivalente_sem_aula_propria(
    cliente: TestClient, db: Session
) -> None:
    """Fecha o achado I2: antes desta correção, `trilha_do_concurso` consultava `Aula` só por
    `topico_id` direto e nunca mostrava "Ver aula" para um tópico equivalente sem aula própria,
    mesmo com `GET /topico/{slug}/aula` servindo a aula normalmente."""
    assert cliente.post("/cadastro", data=CADASTRO, follow_redirects=False).status_code == 303
    tenant_id = _tenant_id(db, CADASTRO["email"])
    edital, alvo = _edital_com_topico_alvo(db, tenant_id, "noc-dir-adm-06-6-improbidade")
    fonte = _topico_com_aula(db, "dir-adm-06-improbidade-administrativa")
    criar_relacao_equivalente(
        db, de_id=fonte.id, para_id=alvo.id, evidencia="ambos citam a Lei nº 8.429/1992"
    )
    db.commit()

    resposta = cliente.get(f"/concurso/{edital.concurso_id}/trilha")

    assert resposta.status_code == 200
    assert f"/topico/{alvo.slug}/aula" in resposta.text
    assert "Ver aula" in resposta.text


def test_trilha_avisa_cobertura_parcial_quando_a_aula_vem_de_subconjunto(
    cliente: TestClient, db: Session
) -> None:
    """I1 propagado à tela: quando a aula só existe por `subconjunto_curado`, a trilha mostra a
    aula (não sumir) **e** avisa que cobre só parte do item."""
    assert cliente.post("/cadastro", data=CADASTRO, follow_redirects=False).status_code == 303
    tenant_id = _tenant_id(db, CADASTRO["email"])
    edital, alvo = _edital_com_topico_alvo(db, tenant_id, "noc-dir-pro-civ-07-recursos")
    fonte = _topico_com_aula(db, "dir-pro-civ-05-recursos-apelacao")
    criar_relacao_subconjunto(
        db, de_id=fonte.id, para_id=alvo.id, evidencia="cobre só apelação/agravo/embargos"
    )
    db.commit()

    resposta = cliente.get(f"/concurso/{edital.concurso_id}/trilha")

    assert resposta.status_code == 200
    assert f"/topico/{alvo.slug}/aula" in resposta.text
    assert "cobre parte" in resposta.text.lower()
