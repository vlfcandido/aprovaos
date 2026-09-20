# O que é: testes do passo 13 da V2 — `GET /concurso/{id}` (DNA reduzido + edital verticalizado,
# 404/403/422 em JSON, só o dono do tenant) e o filtro Jinja `pct`. Quando ler: ao mexer na página
# do concurso (`editais/concurso.html`), em `api/editais.py` ou em `formatar_pct`.
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from aprovaos.api import editais
from aprovaos.api.editais import _nome_exibicao
from aprovaos.api.templates import formatar_pct
from aprovaos.config import Configuracoes
from aprovaos.dados.modelos import Topico, Usuario
from aprovaos.dominio.dna import DnaConcurso, montar_dna_por_regras
from aprovaos.dominio.edital import extrair_conteudo_programatico
from aprovaos.main import criar_app
from tests.test_rota_questoes import _criar_questao, _documento
from tests.test_rota_subir_edital import CADASTRO, FIXTURE_MD, PDF, AnalistaFalso

MATERIAS_DO_CONTEUDO = [
    "Língua Portuguesa",
    "Raciocínio Lógico",
    "Legislação Municipal",
    "Direito Constitucional",
    "Direito Administrativo",
    "Direito Civil",
    "Direito Processual Civil",
]


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


def test_concurso_sem_login_redireciona(cliente: TestClient, pagina: str) -> None:
    cliente.cookies.clear()
    resposta = cliente.get(pagina, follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_concurso_inexistente_404_json(cliente: TestClient, pagina: str) -> None:
    resposta = cliente.get(f"/concurso/{uuid4()}")
    assert resposta.status_code == 404
    corpo = resposta.json()
    assert corpo["codigo"] == "nao_encontrado"
    assert set(corpo) == {"codigo", "mensagem", "acao"}


def test_concurso_de_outro_tenant_403_json(cliente: TestClient, pagina: str) -> None:
    cliente.cookies.clear()
    outra = {"email": "outra@exemplo.com", "senha": "12345678"}
    assert cliente.post("/cadastro", data=outra, follow_redirects=False).status_code == 303
    resposta = cliente.get(pagina)
    assert resposta.status_code == 403
    corpo = resposta.json()
    assert corpo["codigo"] == "proibido"
    assert "outra conta" in corpo["mensagem"]


def test_concurso_id_invalido(cliente: TestClient, pagina: str) -> None:
    resposta = cliente.get("/concurso/abc")
    assert resposta.status_code == 422
    assert resposta.json()["codigo"] == "dados_invalidos"


def test_concurso_mostra_dna_reduzido(cliente: TestClient, pagina: str) -> None:
    resposta = cliente.get(pagina)
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "CÂMARA MUNICIPAL DE CASCAVEL" in corpo
    assert "ASSESSOR DE GABINETE" in corpo
    assert "FUNDAÇÃO DE APOIO À UNIOESTE" in corpo
    assert "15/11/2026" in corpo
    assert "Língua Portuguesa" in corpo
    assert "12,5 %" in corpo
    assert "75 %" in corpo
    assert "50 % do total de pontos (40 de 80)" in corpo
    assert "nota zero elimina" in corpo
    assert "Gerado por regras" in corpo
    assert "sem GOOGLE_API_KEY" in corpo
    assert "O que este DNA ainda não sabe" in corpo
    assert "incidência por tópico" in corpo
    assert "corte histórico" in corpo
    assert (
        "Sem provas anteriores desta banca na base, o peso por tópico é uniforme dentro da matéria"
        in corpo
    )
    assert 'style="--pct: 12.5"' in corpo
    assert 'href="/editais"' in corpo


def test_concurso_mostra_verticalizado(cliente: TestClient, pagina: str) -> None:
    corpo = cliente.get(pagina).text
    assert "0 de 36" in corpo
    assert corpo.count("não visto") == 36
    for nome in MATERIAS_DO_CONTEUDO:
        assert nome in corpo
    assert "Licitações e contratos" in corpo
    assert corpo.count("<li data-slug=") == 36
    assert 'data-slug="dir-adm-04-licitacoes-contratos"' in corpo
    assert corpo.count("<details open") == 7


def _topico_por_slug(db: Session, slug: str) -> Topico:
    return db.scalars(select(Topico).where(Topico.slug == slug)).one()


def _usuario_por_email(db: Session, email: str) -> Usuario:
    return db.scalars(select(Usuario).where(Usuario.email == email)).one()


def test_concurso_mostra_contagem_e_link(cliente: TestClient, pagina: str, db: Session) -> None:
    topico = _topico_por_slug(db, "dir-adm-04-licitacoes-contratos")
    documento = _documento(db, "prova-concurso-1")
    for numero in (58, 59, 60):
        _criar_questao(db, topico, documento.id, numero_item=numero)

    corpo = cliente.get(pagina).text
    inicio = corpo.index('data-slug="dir-adm-04-licitacoes-contratos"')
    trecho = corpo[inicio : corpo.index("</li>", inicio)]
    assert "3 questões" in trecho
    assert 'href="/topico/dir-adm-04-licitacoes-contratos/questoes"' in trecho

    outro_inicio = corpo.index('data-slug="lin-por-01-compreensao-interpretacao"')
    outro_trecho = corpo[outro_inicio : corpo.index("</li>", outro_inicio)]
    assert "<a href=" not in outro_trecho


def test_contador_de_vistos(cliente: TestClient, pagina: str, db: Session) -> None:
    topico = _topico_por_slug(db, "dir-adm-04-licitacoes-contratos")
    documento = _documento(db, "prova-concurso-2")
    questao = _criar_questao(db, topico, documento.id, numero_item=61)

    resposta = cliente.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "C", "confianca": "certeza", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 200

    corpo = cliente.get(pagina).text
    assert "1 de 36" in corpo


def test_grupo_com_acento(cliente: TestClient, pagina: str) -> None:
    corpo = cliente.get(pagina).text
    assert "CONHECIMENTOS ESPECÍFICOS" in corpo
    assert "Conhecimentos Especificos" not in corpo


def test_concurso_gerado_por_ia(
    config_teste: Configuracoes, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    texto = FIXTURE_MD.read_text(encoding="utf-8")
    dna_bom: DnaConcurso = montar_dna_por_regras(texto, extrair_conteudo_programatico(texto))
    monkeypatch.setattr(
        editais, "criar_analista_adk", lambda config, registrar: AnalistaFalso(dna_bom, registrar)
    )
    config = config_teste.model_copy(update={"google_api_key": SecretStr("chave-falsa")})
    with TestClient(criar_app(config, engine=engine)) as cliente:
        assert cliente.post("/cadastro", data=CADASTRO, follow_redirects=False).status_code == 303
        corpo = cliente.get(_subir(cliente)).text
    assert "Gerado por IA (gemini-3.6-flash)" in corpo
    assert "Gerado por regras" not in corpo


def test_formatar_pct() -> None:
    assert formatar_pct(12.5) == "12,5 %"
    assert formatar_pct(75.0) == "75 %"
    assert formatar_pct(3.409) == "3,4 %"
    assert formatar_pct(6.25) == "6,3 %"
    assert formatar_pct("desconhecido") == "desconhecido"


def test_nome_de_materia_na_tabela_de_pesos_nao_capitaliza_conectivo() -> None:
    """`Noções de Informática`, não `Noções De Informática`.

    `_nome_exibicao` usava `str.title()`, que capitaliza toda palavra — inclusive "de", "da",
    "e" — e quebrava na barra ("Matemática/raciocínio"). A regra correta já existia em
    `dominio.edital.normalizar_materia`, criada quando a mesma matéria aparecia em duas grafias
    no painel. Duas implementações da mesma ideia é a armadilha que o HANDOFF chama de "dois
    nomes para o mesmo conceito": uma foi corrigida e a outra ficou errada.
    """
    assert _nome_exibicao("NOÇÕES DE INFORMÁTICA") == "Noções de Informática"
    assert _nome_exibicao("MATEMÁTICA/RACIOCÍNIO LÓGICO") == "Matemática/Raciocínio Lógico"
    assert _nome_exibicao("LÍNGUA PORTUGUESA E REDAÇÃO") == "Língua Portuguesa e Redação"
