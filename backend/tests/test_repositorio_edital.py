# O que é: testes do passo 11 da V2 — `guardar_pdf` (arquivo por hash) e o repositório de edital
# (concurso/edital/documento/tópicos/DNA, get-or-create de tópico por slug, consultas das páginas).
# Quando ler: ao mexer em `dados/arquivos.py` ou `dados/repositorio_edital.py`.
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.agentes.analista_de_edital import ResultadoDna
from aprovaos.dados.arquivos import guardar_pdf
from aprovaos.dados.modelos import (
    Concurso,
    DnaConcursoRegistro,
    Documento,
    Edital,
    Topico,
    TopicoEdital,
)
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dados.repositorio_edital import (
    DadosDocumento,
    buscar_concurso,
    concurso_principal,
    contagem_editais_com_dna,
    dna_atual,
    edital_atual,
    listar_concursos_do_tenant,
    registrar_edital,
    verticalizado,
)
from aprovaos.dominio.conta import DadosCadastro
from aprovaos.dominio.dna import montar_dna_por_regras
from aprovaos.dominio.edital import (
    MateriaExtraida,
    TopicoExtraido,
    extrair_conteudo_programatico,
)

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_MD = RAIZ / "docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md"
HASH = "ab" * 32


@pytest.fixture
def texto() -> str:
    return FIXTURE_MD.read_text(encoding="utf-8")


@pytest.fixture
def materias(texto: str) -> list[MateriaExtraida]:
    return extrair_conteudo_programatico(texto)


@pytest.fixture
def resultado(texto: str, materias: list[MateriaExtraida]) -> ResultadoDna:
    return ResultadoDna(
        dna=montar_dna_por_regras(texto, materias),
        origem="regras",
        motivo_fallback="sem GOOGLE_API_KEY",
    )


@pytest.fixture
def documento() -> DadosDocumento:
    return DadosDocumento(
        hash=HASH,
        caminho_relativo=f"{HASH}.pdf",
        nome_original="edital.pdf",
        tamanho=3716,
        paginas=1,
    )


def _tenant(db: Session, email: str) -> UUID:
    return criar_conta(db, DadosCadastro(email=email, senha="12345678")).tenant_id


def _contar(db: Session, modelo: type[Concurso | Documento | Topico | TopicoEdital]) -> int:
    return db.scalar(select(func.count()).select_from(modelo)) or 0


def test_guardar_pdf_cria_pasta_e_arquivo(tmp_path: Path) -> None:
    pasta = tmp_path / "u"
    conteudo = b"%PDF-1.4 conteudo"
    caminho = guardar_pdf(pasta, HASH, conteudo)
    assert caminho == pasta / f"{HASH}.pdf"
    assert caminho.read_bytes() == conteudo
    mtime = caminho.stat().st_mtime_ns
    de_novo = guardar_pdf(pasta, HASH, b"%PDF-1.4 outro")
    assert de_novo == caminho
    assert caminho.stat().st_mtime_ns == mtime
    assert caminho.read_bytes() == conteudo


def test_registrar_edital_cria_tudo(
    db: Session,
    resultado: ResultadoDna,
    materias: list[MateriaExtraida],
    documento: DadosDocumento,
) -> None:
    tenant_id = _tenant(db, "linda@exemplo.com")
    concurso = registrar_edital(db, tenant_id, resultado, materias, documento)
    db.commit()

    assert _contar(db, Concurso) == 1
    assert concurso.tenant_id == tenant_id
    assert concurso.orgao == "CÂMARA MUNICIPAL DE CASCAVEL — ESTADO DO PARANÁ"
    assert concurso.cargo == "ASSESSOR DE GABINETE"
    assert concurso.banca == "FUNDAÇÃO DE APOIO À UNIOESTE"
    assert concurso.data_prova == date(2026, 11, 15)

    edital = db.scalars(select(Edital)).one()
    assert edital.concurso_id == concurso.id
    assert edital.versao == 1
    doc = db.scalars(select(Documento)).one()
    assert edital.documento_id == doc.id
    assert doc.tipo == "edital"
    assert doc.hash == HASH
    assert doc.caminho == f"{HASH}.pdf"
    assert doc.metadados == {"nome_original": "edital.pdf", "tamanho": 3716, "paginas": 1}

    assert _contar(db, Topico) == 36
    linhas = db.scalars(
        select(TopicoEdital).where(TopicoEdital.edital_id == edital.id).order_by(TopicoEdital.ordem)
    ).all()
    assert [linha.ordem for linha in linhas] == list(range(1, 37))
    assert linhas[0].texto_original == "1. Compreensão e interpretação de textos."
    assert linhas[0].peso_edital == Decimal("1.786")  # 12,5 % / 7 tópicos
    assert linhas[0].topico.slug == "lin-por-01-compreensao-interpretacao"
    assert linhas[0].topico.materia == "LÍNGUA PORTUGUESA"
    assert linhas[0].topico.nome == "Compreensão e interpretação de textos."
    licitacoes = next(t for t in linhas if t.topico.slug.endswith("licitacoes-contratos"))
    assert licitacoes.peso_edital == Decimal("3.409")  # 75 % / 22 tópicos

    registro = db.scalars(select(DnaConcursoRegistro)).one()
    assert registro.concurso_id == concurso.id
    assert registro.versao == 1
    assert registro.origem == "regras"
    assert registro.modelo is None
    assert registro.motivo_fallback == "sem GOOGLE_API_KEY"
    assert registro.conteudo == resultado.dna.model_dump(mode="json")


def test_registrar_edital_guarda_grupo(
    db: Session, resultado: ResultadoDna, materias: list[MateriaExtraida], documento: DadosDocumento
) -> None:
    """P-26: `topico_edital.grupo` vem de `MateriaExtraida.grupo`, não é derivado do slug."""
    tenant_id = _tenant(db, "linda@exemplo.com")
    concurso = registrar_edital(db, tenant_id, resultado, materias, documento)
    db.commit()
    edital = edital_atual(db, concurso.id)
    assert edital is not None
    linhas = db.scalars(
        select(TopicoEdital).where(TopicoEdital.edital_id == edital.id).order_by(TopicoEdital.ordem)
    ).all()
    grupos_por_materia = {linha.topico.materia: linha.grupo for linha in linhas}
    assert grupos_por_materia["LÍNGUA PORTUGUESA"] is None
    assert grupos_por_materia["RACIOCÍNIO LÓGICO"] is None
    assert grupos_por_materia["LEGISLAÇÃO MUNICIPAL"] is None
    assert grupos_por_materia["DIREITO CONSTITUCIONAL"] == "CONHECIMENTOS ESPECÍFICOS"
    assert grupos_por_materia["DIREITO ADMINISTRATIVO"] == "CONHECIMENTOS ESPECÍFICOS"
    assert grupos_por_materia["DIREITO CIVIL"] == "CONHECIMENTOS ESPECÍFICOS"
    assert grupos_por_materia["DIREITO PROCESSUAL CIVIL"] == "CONHECIMENTOS ESPECÍFICOS"


def test_registrar_edital_por_ia_guarda_modelo_e_data_desconhecida(
    db: Session, resultado: ResultadoDna, materias: list[MateriaExtraida], documento: DadosDocumento
) -> None:
    dna = resultado.dna.model_copy(deep=True)
    dna.concurso.data_prova = "desconhecido"
    por_ia = ResultadoDna(dna=dna, origem="ia", motivo_fallback=None)
    concurso = registrar_edital(
        db, _tenant(db, "a@exemplo.com"), por_ia, materias, documento, modelo="gemini-2.5-flash"
    )
    db.commit()
    assert concurso.data_prova is None
    registro = db.scalars(select(DnaConcursoRegistro)).one()
    assert registro.origem == "ia"
    assert registro.modelo == "gemini-2.5-flash"
    assert registro.motivo_fallback is None


def test_registrar_edital_reaproveita_topico_por_slug(
    db: Session, resultado: ResultadoDna, materias: list[MateriaExtraida], documento: DadosDocumento
) -> None:
    tenant_id = _tenant(db, "linda@exemplo.com")
    registrar_edital(db, tenant_id, resultado, materias, documento)
    registrar_edital(db, tenant_id, resultado, materias, documento)
    db.commit()
    assert _contar(db, Concurso) == 2
    assert _contar(db, Topico) == 36
    assert _contar(db, TopicoEdital) == 72


def test_listar_concursos_do_tenant(
    db: Session, resultado: ResultadoDna, materias: list[MateriaExtraida], documento: DadosDocumento
) -> None:
    tenant_a = _tenant(db, "a@exemplo.com")
    tenant_b = _tenant(db, "b@exemplo.com")
    tenant_c = _tenant(db, "c@exemplo.com")
    primeiro = registrar_edital(db, tenant_a, resultado, materias, documento)
    segundo = registrar_edital(db, tenant_a, resultado, materias, documento)
    registrar_edital(db, tenant_b, resultado, materias, documento)
    db.commit()
    # Garante ordem estável por `criado_em` mesmo com inserções no mesmo instante.
    primeiro.criado_em = primeiro.criado_em.replace(year=2025)
    db.commit()

    lista = listar_concursos_do_tenant(db, tenant_a)
    assert [c.id for c in lista] == [segundo.id, primeiro.id]
    principal = concurso_principal(db, tenant_a)
    assert principal is not None
    assert principal.id == segundo.id
    assert concurso_principal(db, tenant_c) is None
    assert listar_concursos_do_tenant(db, tenant_c) == []


def test_buscar_concurso_e_verticalizado(
    db: Session, resultado: ResultadoDna, materias: list[MateriaExtraida], documento: DadosDocumento
) -> None:
    concurso = registrar_edital(db, _tenant(db, "a@exemplo.com"), resultado, materias, documento)
    db.commit()

    assert buscar_concurso(db, uuid4()) is None
    achado = buscar_concurso(db, concurso.id)
    assert achado is not None
    assert achado.id == concurso.id

    edital = edital_atual(db, concurso.id)
    assert edital is not None
    assert edital.versao == 1
    assert edital_atual(db, uuid4()) is None

    registro = dna_atual(db, concurso.id)
    assert registro is not None
    assert registro.versao == 1
    assert dna_atual(db, uuid4()) is None

    lista = verticalizado(db, edital.id)
    assert [m.nome for m in lista] == [
        "LÍNGUA PORTUGUESA",
        "RACIOCÍNIO LÓGICO",
        "LEGISLAÇÃO MUNICIPAL",
        "DIREITO CONSTITUCIONAL",
        "DIREITO ADMINISTRATIVO",
        "DIREITO CIVIL",
        "DIREITO PROCESSUAL CIVIL",
    ]
    assert [m.slug for m in lista][:2] == ["lingua-portuguesa", "raciocinio-logico"]
    assert [len(m.topicos) for m in lista] == [7, 4, 3, 6, 7, 4, 5]
    assert sum(len(m.topicos) for m in lista) == 36
    primeiro = lista[0].topicos[0]
    assert primeiro.slug == "lin-por-01-compreensao-interpretacao"
    assert primeiro.texto_original == "1. Compreensão e interpretação de textos."
    assert primeiro.status == "não visto"
    assert lista[4].topicos[3].texto_original == "4. Licitações e contratos — Lei nº 14.133/2021."


def test_slug_igual_com_conteudo_diferente_nao_funde_dois_editais(
    db: Session, resultado: ResultadoDna, documento: DadosDocumento
) -> None:
    """Mesmo slug com matéria/nome diferentes vira dois tópicos, não um só.

    O defeito real que este teste tranca (achado em 19/09/2026 no `dev.db`): o edital fictício de
    Cascavel escreve `LÍNGUA PORTUGUESA` com o item "Compreensão e interpretação de textos." e o
    edital real do TJ-PR escreve `Língua Portuguesa` com "Compreensão e interpretação de texto.".
    Os dois produzem `lin-por-01-compreensao-interpretacao`; com get-or-create só por slug, o item
    do edital **real** virava silenciosamente o tópico do edital **fictício** — conteúdo cruzando
    entre editais sem a relação curada que a ADR-0041 existe para exigir.
    """
    tenant_id = _tenant(db, "linda@exemplo.com")
    caixa_alta = [
        MateriaExtraida(
            nome="LÍNGUA PORTUGUESA",
            slug="lingua-portuguesa",
            grupo=None,
            topicos=[
                TopicoExtraido(
                    numero=1,
                    texto_original="1. Compreensão e interpretação de textos.",
                    slug="lin-por-01-compreensao-interpretacao",
                )
            ],
        )
    ]
    titulo_caso = [
        MateriaExtraida(
            nome="Língua Portuguesa",
            slug="lingua-portuguesa",
            grupo=None,
            topicos=[
                TopicoExtraido(
                    numero=1,
                    texto_original="1. Compreensão e interpretação de texto.",
                    slug="lin-por-01-compreensao-interpretacao",
                )
            ],
        )
    ]
    registrar_edital(db, tenant_id, resultado, caixa_alta, documento)
    registrar_edital(db, tenant_id, resultado, titulo_caso, documento)
    db.commit()

    topicos = list(db.scalars(select(Topico).order_by(Topico.criado_em)))
    assert len(topicos) == 2, [(t.slug, t.materia, t.nome) for t in topicos]
    assert topicos[0].slug == "lin-por-01-compreensao-interpretacao"
    assert topicos[0].materia == "LÍNGUA PORTUGUESA"
    assert topicos[0].nome == "Compreensão e interpretação de textos."
    assert topicos[1].slug == "lin-por-01-compreensao-interpretacao-2"
    assert topicos[1].materia == "Língua Portuguesa"
    assert topicos[1].nome == "Compreensão e interpretação de texto."


def test_slug_igual_com_conteudo_identico_continua_reaproveitando(
    db: Session, resultado: ResultadoDna, documento: DadosDocumento
) -> None:
    """Identidade de verdade (mesma matéria, mesmo nome) continua compartilhando um tópico só.

    A premissa D (vocabulário global) não morre: ela passa a valer para o que é realmente o mesmo
    item, não para o que apenas colide de slug.
    """
    tenant_id = _tenant(db, "linda@exemplo.com")
    materia = [
        MateriaExtraida(
            nome="Língua Portuguesa",
            slug="lingua-portuguesa",
            grupo=None,
            topicos=[
                TopicoExtraido(
                    numero=1,
                    texto_original="1. Compreensão e interpretação de texto.",
                    slug="lin-por-01-compreensao-interpretacao",
                )
            ],
        )
    ]
    registrar_edital(db, tenant_id, resultado, materia, documento)
    registrar_edital(db, tenant_id, resultado, materia, documento)
    db.commit()

    assert _contar(db, Topico) == 1
    assert _contar(db, TopicoEdital) == 2


def test_registrar_edital_nasce_real_e_aceita_fixture(
    db: Session, resultado: ResultadoDna, materias: list[MateriaExtraida], documento: DadosDocumento
) -> None:
    """`origem` nasce `"real"`; PDF de teste é marcado explicitamente (P-62)."""
    tenant_id = _tenant(db, "linda@exemplo.com")
    real = registrar_edital(db, tenant_id, resultado, materias, documento)
    teste = registrar_edital(db, tenant_id, resultado, materias, documento, origem="fixture")
    db.commit()
    assert real.origem == "real"
    assert teste.origem == "fixture"


def test_contagem_editais_com_dna(
    db: Session, resultado: ResultadoDna, materias: list[MateriaExtraida], documento: DadosDocumento
) -> None:
    """Conta concursos **distintos** com `dna_concurso` — ADR-0015: Free processa só 1."""
    tenant_id = _tenant(db, "linda@exemplo.com")
    outro_tenant_id = _tenant(db, "outra@exemplo.com")
    assert contagem_editais_com_dna(db, tenant_id) == 0

    registrar_edital(db, tenant_id, resultado, materias, documento)
    db.commit()
    assert contagem_editais_com_dna(db, tenant_id) == 1

    registrar_edital(db, tenant_id, resultado, materias, documento)
    db.commit()
    assert contagem_editais_com_dna(db, tenant_id) == 2
    assert contagem_editais_com_dna(db, outro_tenant_id) == 0
