# O que é: testes do passo 3 da V1 e do passo 2 da V2 — mapeamento ORM das tabelas base e das
# tabelas de edital/DNA. Quando ler: ao alterar coluna/constraint delas ou o `DataHoraUtc`.
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from aprovaos.dados.base import Base
from aprovaos.dados.modelos import (
    Concurso,
    DnaConcursoRegistro,
    Documento,
    Edital,
    Sessao,
    Tenant,
    Topico,
    TopicoEdital,
    Usuario,
)


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as sessao:
        yield sessao
    Base.metadata.drop_all(engine)
    engine.dispose()


def _conta(db: Session) -> tuple[Tenant, Usuario, Sessao]:
    tenant = Tenant(tipo="pf", nome="Linda")
    usuario = Usuario(email="linda@exemplo.com", senha_hash="h", tenant=tenant)
    expira = datetime.now(UTC) + timedelta(days=30)
    sessao = Sessao(usuario=usuario, token_hash="a" * 64, expira_em=expira)
    db.add_all([tenant, usuario, sessao])
    db.commit()
    return tenant, usuario, sessao


def test_tabelas() -> None:
    assert set(Base.metadata.tables) == {
        "tenant",
        "usuario",
        "sessao",
        "traco",
        "concurso",
        "edital",
        "documento",
        "topico",
        "topico_edital",
        "dna_concurso",
    }


def _colunas(tabela: str) -> set[str]:
    return {c.key for c in Base.metadata.tables[tabela].columns}


def test_colunas_padrao() -> None:
    for tabela in ("tenant", "usuario", "sessao"):
        assert {"id", "criado_em", "atualizado_em"} <= _colunas(tabela), tabela
    assert {"id", "criado_em"} <= _colunas("traco")


def test_insere_tenant_usuario_sessao(db: Session) -> None:
    tenant, usuario, sessao = _conta(db)
    assert isinstance(usuario.id, uuid.UUID)
    assert isinstance(tenant.id, uuid.UUID)
    assert isinstance(sessao.id, uuid.UUID)
    assert usuario.criado_em.tzinfo is not None
    assert usuario.atualizado_em.tzinfo is not None
    assert usuario.tenant_id == tenant.id
    assert sessao.usuario_id == usuario.id


def test_email_unico(db: Session) -> None:
    tenant, _, _ = _conta(db)
    db.add(Usuario(email="linda@exemplo.com", senha_hash="h2", tenant=tenant))
    with pytest.raises(IntegrityError):
        db.commit()


def test_tipo_do_tenant_restrito(db: Session) -> None:
    db.add(Tenant(tipo="xx", nome="errado"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_datahora_volta_aware_do_sqlite(db: Session) -> None:
    _, _, sessao = _conta(db)
    gravado = sessao.expira_em
    db.expire_all()
    lido = db.get(Sessao, sessao.id)
    assert lido is not None
    assert lido.expira_em.tzinfo is not None
    assert lido.expira_em == gravado.astimezone(UTC)
    assert lido.expira_em > datetime.now(UTC)


def test_traco_colunas_minimas() -> None:
    esperadas = {
        "iniciado_em",
        "duracao_ms",
        "usuario_id",
        "agente",
        "modelo",
        "tokens_in",
        "tokens_out",
        "custo_brl",
        "tier",
        "resultado",
        "erro",
        "span_pai_id",
    }
    assert esperadas <= _colunas("traco")


def _edital_completo(db: Session) -> tuple[Tenant, Concurso, Edital, Topico, DnaConcursoRegistro]:
    agora = datetime.now(UTC)
    tenant = Tenant(tipo="pf", nome="Linda")
    documento = Documento(
        tipo="edital", hash="a" * 64, caminho="a.pdf", baixado_em=agora, metadados={"paginas": 1}
    )
    concurso = Concurso(tenant=tenant, orgao="Câmara", cargo="Assessor", banca="desconhecido")
    edital = Edital(concurso=concurso, versao=1, documento=documento)
    topico = Topico(
        materia="direito-administrativo",
        nome="Licitações",
        slug="dir-adm-04-licitacoes-contratos",
    )
    topico_edital = TopicoEdital(
        edital=edital,
        topico=topico,
        ordem=4,
        texto_original="4. Licitações e contratos — Lei nº 14.133/2021.",
        peso_edital=Decimal("3.409"),
    )
    dna = DnaConcursoRegistro(
        concurso=concurso, versao=1, gerado_em=agora, origem="regras", conteudo={"versao": 1}
    )
    db.add_all([tenant, documento, concurso, edital, topico, topico_edital, dna])
    db.commit()
    return tenant, concurso, edital, topico, dna


def test_insere_concurso_edital_documento_topicos_dna(db: Session) -> None:
    tenant, concurso, edital, topico, dna = _edital_completo(db)
    assert isinstance(edital.id, uuid.UUID)
    assert concurso.tenant_id == tenant.id
    assert edital.documento.tipo == "edital"
    assert edital.documento.metadados == {"paginas": 1}
    assert dna.conteudo["versao"] == 1
    assert dna.gerado_em.tzinfo is not None
    db.expire_all()
    lido = db.scalars(select(TopicoEdital)).one()
    assert lido.topico_id == topico.id
    assert lido.peso_edital == Decimal("3.409")
    assert lido.ordem == 4


def test_concurso_sem_tenant_e_permitido(db: Session) -> None:
    db.add(Concurso(tenant_id=None, orgao="TCU", cargo="Auditor", banca="Cebraspe"))
    db.commit()
    assert db.scalars(select(Concurso)).one().tenant_id is None


def test_slug_de_topico_unico(db: Session) -> None:
    _edital_completo(db)
    db.add(Topico(materia="x", nome="y", slug="dir-adm-04-licitacoes-contratos"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_topico_edital_unico_por_edital(db: Session) -> None:
    _, _, edital, topico, _ = _edital_completo(db)
    db.add(TopicoEdital(edital=edital, topico=topico, ordem=5, texto_original="repetido"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_origem_do_dna_restrita(db: Session) -> None:
    _, concurso, _, _, _ = _edital_completo(db)
    db.add(
        DnaConcursoRegistro(
            concurso=concurso, versao=2, gerado_em=datetime.now(UTC), origem="xx", conteudo={}
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_tipo_do_documento_restrito(db: Session) -> None:
    db.add(
        Documento(
            tipo="foto", hash="b" * 64, caminho="b.pdf", baixado_em=datetime.now(UTC), metadados={}
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
