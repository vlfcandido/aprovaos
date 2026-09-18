# O que é: testes do passo 12 da V2 — `GET/POST /editais/subir` (formulário multipart, pipeline
# PDF → parser → DNA → persistência, redirecionamento, 4 erros re-renderizados, IA por dublê e
# teto diário). Quando ler: ao mexer em `api/editais.py` ou em `editais/subir.html`.
import re
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from aprovaos.api import editais
from aprovaos.config import Configuracoes
from aprovaos.dados.modelos import Concurso, DnaConcursoRegistro, TopicoEdital, Traco, Usuario
from aprovaos.dados.repositorio_traco import registrar_traco
from aprovaos.dominio.dna import DnaConcurso, montar_dna_por_regras
from aprovaos.dominio.edital import MateriaExtraida, extrair_conteudo_programatico
from aprovaos.dominio.pdf import LIMITE_BYTES
from aprovaos.main import criar_app
from aprovaos.roteador.custo import ChamadaLlm

RAIZ = Path(__file__).resolve().parents[2]
PDF = (RAIZ / "knowledge/fixtures/editais/edital-assessor-gabinete.pdf").read_bytes()
FIXTURE_MD = RAIZ / "docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md"
CADASTRO = {"email": "linda@exemplo.com", "senha": "12345678"}
AGORA = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


class AnalistaFalso:
    """Dublê da porta: devolve o DNA dado e registra uma `ChamadaLlm` como o ADK faria."""

    def __init__(self, dna: DnaConcurso, registrar: Callable[[ChamadaLlm], None]) -> None:
        self.dna = dna
        self.registrar = registrar

    async def analisar(self, texto: str, materias: list[MateriaExtraida]) -> DnaConcurso:
        self.registrar(
            ChamadaLlm(
                agente="analista-de-edital",
                modelo="gemini-2.5-flash",
                iniciado_em=AGORA,
                duracao_ms=1500,
                tokens_in=60_000,
                tokens_out=8_000,
                custo_brl=Decimal("0.205200"),
                resultado="ok",
            )
        )
        return self.dna


@pytest.fixture
def logado(cliente: TestClient) -> TestClient:
    resposta = cliente.post("/cadastro", data=CADASTRO, follow_redirects=False)
    assert resposta.status_code == 303
    return cliente


@pytest.fixture
def dna_bom() -> DnaConcurso:
    texto = FIXTURE_MD.read_text(encoding="utf-8")
    return montar_dna_por_regras(texto, extrair_conteudo_programatico(texto))


@pytest.fixture
def app_com_chave(config_teste: Configuracoes, engine: Engine) -> Iterator[TestClient]:
    config = config_teste.model_copy(update={"google_api_key": SecretStr("chave-falsa")})
    with TestClient(criar_app(config, engine=engine)) as cliente:
        resposta = cliente.post("/cadastro", data=CADASTRO, follow_redirects=False)
        assert resposta.status_code == 303
        yield cliente


def _contar(db: Session, modelo: type[Concurso | TopicoEdital | Traco]) -> int:
    return db.scalar(select(func.count()).select_from(modelo)) or 0


def test_get_subir_sem_login_redireciona(cliente: TestClient) -> None:
    resposta = cliente.get("/editais/subir", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_get_subir(logado: TestClient) -> None:
    resposta = logado.get("/editais/subir")
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "<form" in corpo
    assert 'method="post"' in corpo
    assert 'enctype="multipart/form-data"' in corpo
    assert 'hx-post="/editais/subir"' in corpo
    assert 'hx-encoding="multipart/form-data"' in corpo
    assert 'hx-select="#form-edital"' in corpo
    assert 'hx-target="#form-edital"' in corpo
    assert 'hx-swap="outerHTML"' in corpo
    assert re.search(
        r'<input[^>]*type="file"[^>]*name="arquivo"[^>]*accept="application/pdf"[^>]*required',
        corpo,
    )
    assert "10 MB" in corpo


def test_post_subir_cria_concurso_e_redireciona(
    logado: TestClient, db: Session, config_teste: Configuracoes
) -> None:
    resposta = logado.post(
        "/editais/subir",
        files={"arquivo": ("edital.pdf", PDF, "application/pdf")},
        follow_redirects=False,
    )
    assert resposta.status_code == 303
    assert re.fullmatch(r"/concurso/[0-9a-f-]{36}", resposta.headers["location"])

    usuario = db.scalars(select(Usuario)).one()
    concurso = db.scalars(select(Concurso)).one()
    assert concurso.tenant_id == usuario.tenant_id
    assert resposta.headers["location"] == f"/concurso/{concurso.id}"
    assert _contar(db, TopicoEdital) == 36
    registro = db.scalars(select(DnaConcursoRegistro)).one()
    assert registro.origem == "regras"
    assert registro.motivo_fallback == "sem GOOGLE_API_KEY"
    assert registro.modelo is None
    assert _contar(db, Traco) == 0

    assert config_teste.uploads_dir is not None
    arquivos = list(config_teste.uploads_dir.glob("*.pdf"))
    assert len(arquivos) == 1
    assert re.fullmatch(r"[0-9a-f]{64}\.pdf", arquivos[0].name)
    assert arquivos[0].read_bytes() == PDF


def test_post_subir_htmx(logado: TestClient, db: Session) -> None:
    resposta = logado.post(
        "/editais/subir",
        files={"arquivo": ("edital.pdf", PDF, "application/pdf")},
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    assert resposta.status_code == 200
    concurso = db.scalars(select(Concurso)).one()
    assert resposta.headers["hx-redirect"] == f"/concurso/{concurso.id}"


def test_post_subir_sem_login_redireciona(cliente: TestClient) -> None:
    resposta = cliente.post(
        "/editais/subir",
        files={"arquivo": ("edital.pdf", PDF, "application/pdf")},
        follow_redirects=False,
    )
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_post_subir_nao_pdf(logado: TestClient, db: Session, config_teste: Configuracoes) -> None:
    resposta = logado.post(
        "/editais/subir",
        files={"arquivo": ("foto.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        follow_redirects=False,
    )
    assert resposta.status_code == 200
    assert "Envie um arquivo PDF" in resposta.text
    assert 'id="form-edital"' in resposta.text
    assert _contar(db, Concurso) == 0
    assert config_teste.uploads_dir is not None
    assert not config_teste.uploads_dir.exists()


def test_post_subir_grande(logado: TestClient, db: Session) -> None:
    grande = b"%PDF-" + b"x" * (LIMITE_BYTES + 1 - 5)
    resposta = logado.post(
        "/editais/subir",
        files={"arquivo": ("edital.pdf", grande, "application/pdf")},
        follow_redirects=False,
    )
    assert resposta.status_code == 200
    assert "10 MB" in resposta.text
    assert _contar(db, Concurso) == 0


def test_post_subir_sem_conteudo_programatico(
    logado: TestClient, db: Session, tmp_path: Path
) -> None:
    destino = tmp_path / "ola.pdf"
    SimpleDocTemplate(str(destino), pagesize=A4).build(
        [Paragraph("OLÁ", getSampleStyleSheet()["Normal"])]
    )
    resposta = logado.post(
        "/editais/subir",
        files={"arquivo": ("ola.pdf", destino.read_bytes(), "application/pdf")},
        follow_redirects=False,
    )
    assert resposta.status_code == 200
    assert "conteúdo programático" in resposta.text
    assert _contar(db, Concurso) == 0


def test_post_subir_usa_ia_quando_ha_chave_e_teto(
    app_com_chave: TestClient,
    db: Session,
    dna_bom: DnaConcurso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        editais,
        "criar_analista_adk",
        lambda config, registrar: AnalistaFalso(dna_bom, registrar),
    )
    resposta = app_com_chave.post(
        "/editais/subir",
        files={"arquivo": ("edital.pdf", PDF, "application/pdf")},
        follow_redirects=False,
    )
    assert resposta.status_code == 303
    registro = db.scalars(select(DnaConcursoRegistro)).one()
    assert registro.origem == "ia"
    assert registro.modelo == "gemini-3.6-flash"
    assert registro.motivo_fallback is None
    usuario = db.scalars(select(Usuario)).one()
    traco = db.scalars(select(Traco)).one()
    assert traco.usuario_id == usuario.id
    assert traco.custo_brl == Decimal("0.205200")
    assert traco.agente == "analista-de-edital"


def test_post_subir_teto_estourado_usa_regras(
    app_com_chave: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    registrar_traco(
        db,
        ChamadaLlm(
            agente="analista-de-edital",
            modelo="gemini-2.5-flash",
            iniciado_em=datetime.now(UTC),
            duracao_ms=1,
            tokens_in=1,
            tokens_out=1,
            custo_brl=Decimal("3.00"),
            resultado="ok",
        ),
        usuario_id=None,
    )
    db.commit()
    chamadas: list[Configuracoes] = []

    def fabrica_proibida(config: Configuracoes, registrar: Callable[[ChamadaLlm], None]) -> None:
        chamadas.append(config)
        raise AssertionError("criar_analista_adk não deveria ser chamado com o teto estourado")

    monkeypatch.setattr(editais, "criar_analista_adk", fabrica_proibida)
    resposta = app_com_chave.post(
        "/editais/subir",
        files={"arquivo": ("edital.pdf", PDF, "application/pdf")},
        follow_redirects=False,
    )
    assert resposta.status_code == 303
    assert chamadas == []
    registro = db.scalars(select(DnaConcursoRegistro)).one()
    assert registro.origem == "regras"
    assert registro.motivo_fallback == "teto diário atingido"
    assert _contar(db, Traco) == 1
