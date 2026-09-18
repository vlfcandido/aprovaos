# O que é: testes do passo 3 da V1 — mapeamento ORM de tenant, usuario, sessao e traco.
# Quando ler: ao alterar coluna/constraint dessas tabelas ou o TypeDecorator `DataHoraUtc`.
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from aprovaos.dados.base import Base
from aprovaos.dados.modelos import Sessao, Tenant, Usuario


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


def test_tabelas_da_v1() -> None:
    assert set(Base.metadata.tables) == {"tenant", "usuario", "sessao", "traco"}


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
