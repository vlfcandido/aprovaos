# O que é: testes do passo 3 da V1, do passo 2 da V2, do passo 10 da V3 e do passo 1 da fundação
# jurídica — mapeamento ORM das tabelas base, de edital/DNA, de questões/eventos e de
# dispositivo_legal/citacao. Quando ler: ao alterar coluna/constraint delas ou o `DataHoraUtc`.
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
    Alternativa,
    Citacao,
    Concurso,
    DispositivoLegal,
    DnaConcursoRegistro,
    Documento,
    DossieTopico,
    Edital,
    EventoEstudo,
    Fonte,
    Questao,
    ReporteErro,
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
        "fonte",
        "questao",
        "alternativa",
        "evento_estudo",
        "reporte_erro",
        "dispositivo_legal",
        "citacao",
        "dossie_topico",
        "cartao",
        "aula",
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


def _origem_json() -> dict[str, object]:
    """Os 8 campos de `Origem` (`dominio/questao.py`), já como dict pronto para a coluna JSON."""
    return {
        "banca": "cebraspe",
        "orgao": "TJ-PA",
        "cargo": "Analista Judiciário",
        "ano": 2025,
        "numero_item": 58,
        "tipo_caderno": None,
        "url_prova": "https://cdn.cebraspe.org.br/prova.pdf",
        "documento_id": str(uuid.uuid4()),
    }


def test_insere_fonte_questao_evento_reporte(db: Session) -> None:
    tenant, usuario, _ = _conta(db)
    fonte = Fonte(
        id_externo="cebraspe",
        nome="Cebraspe — Centro Brasileiro de Pesquisa em Avaliação e Seleção",
        url_lista="https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos/fase/encerrado",
        status="ativa",
    )
    concurso = Concurso(tenant=tenant, orgao="TJ-PA", cargo="Analista", banca="cebraspe")
    documento = Documento(
        tipo="prova",
        hash="c" * 64,
        caminho="c.pdf",
        baixado_em=datetime.now(UTC),
        metadados={},
    )
    topico = Topico(materia="direito-civil", nome="Prescrição", slug="dir-civ-01-prescricao")
    questao = Questao(
        adapter="concursos",
        banca="cebraspe",
        tipo_item="certo_errado",
        comando="Julgue o item a seguir.",
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado="O prazo prescricional é de 5 anos.",
        gabarito_preliminar=None,
        gabarito="C",
        gabarito_status="definitivo",
        publicavel=True,
        motivo_nao_publicavel=None,
        regra_prova={"anula_por_erro": True, "fonte": "instrução do caderno"},
        topico=topico,
        topico_confianca="alta",
        topico_evidencia="menciona prescrição",
        origem=_origem_json(),
        documento=documento,
        hash_dedup="a" * 40,
        dificuldade_est=None,
        discriminacao_est=None,
    )
    evento = EventoEstudo(
        usuario_id=usuario.id,
        ocorrido_em=datetime.now(UTC),
        tipo="resposta",
        questao=questao,
        acertou=True,
        resposta="C",
        confianca_declarada="certeza",
        tempo_ms=4200,
    )
    reporte = ReporteErro(
        usuario_id=usuario.id,
        conteudo_tipo="questao",
        conteudo_id=uuid.uuid4(),
        motivo="gabarito parece errado",
        status="aberto",
    )
    db.add_all([fonte, concurso, documento, topico, questao, evento, reporte])
    db.commit()

    for linha in (fonte, questao, evento, reporte):
        assert isinstance(linha.id, uuid.UUID)
    assert questao.publicada is False
    assert questao.inedita is False


def test_hash_dedup_unico(db: Session) -> None:
    documento = Documento(
        tipo="prova", hash="d" * 64, caminho="d.pdf", baixado_em=datetime.now(UTC), metadados={}
    )
    dados_comuns: dict[str, object] = {
        "adapter": "concursos",
        "banca": "cebraspe",
        "tipo_item": "certo_errado",
        "comando": None,
        "texto_apoio": None,
        "texto_apoio_itens": [],
        "gabarito_preliminar": None,
        "gabarito": "C",
        "gabarito_status": "definitivo",
        "publicavel": True,
        "motivo_nao_publicavel": None,
        "regra_prova": {"anula_por_erro": True, "fonte": "instrução do caderno"},
        "topico_confianca": "media",
        "topico_evidencia": "sem correspondência",
        "origem": _origem_json(),
        "documento": documento,
        "hash_dedup": "b" * 40,
    }
    db.add(Questao(enunciado="Enunciado 1.", **dados_comuns))
    db.commit()
    db.add(Questao(enunciado="Enunciado 2 (repetido de propósito).", **dados_comuns))
    with pytest.raises(IntegrityError):
        db.commit()


def test_evento_estudo_valida_tipo(db: Session) -> None:
    _, usuario, _ = _conta(db)
    db.add(EventoEstudo(usuario_id=usuario.id, ocorrido_em=datetime.now(UTC), tipo="qualquer"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_gabarito_status_do_evento_reporte_status_restritos(db: Session) -> None:
    _, usuario, _ = _conta(db)
    documento = Documento(
        tipo="prova", hash="e" * 64, baixado_em=datetime.now(UTC), caminho="e.pdf", metadados={}
    )
    db.add(
        Questao(
            adapter="concursos",
            banca="cebraspe",
            tipo_item="certo_errado",
            comando=None,
            texto_apoio=None,
            texto_apoio_itens=[],
            enunciado="X",
            gabarito_preliminar=None,
            gabarito=None,
            gabarito_status="xx",
            publicavel=False,
            motivo_nao_publicavel="sem gabarito",
            regra_prova={"anula_por_erro": True, "fonte": "instrução do caderno"},
            topico_confianca="baixa",
            topico_evidencia="",
            origem=_origem_json(),
            documento=documento,
            hash_dedup="f" * 40,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    db.add(
        ReporteErro(
            usuario_id=usuario.id,
            conteudo_tipo="questao",
            conteudo_id=uuid.uuid4(),
            motivo="x",
            status="xx",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_alternativa_ligada_a_questao(db: Session) -> None:
    documento = Documento(
        tipo="prova", hash="g" * 64, baixado_em=datetime.now(UTC), caminho="g.pdf", metadados={}
    )
    questao = Questao(
        adapter="concursos",
        banca="fgv",
        tipo_item="multipla_escolha",
        comando=None,
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado="Marque a alternativa correta.",
        gabarito_preliminar=None,
        gabarito=None,
        gabarito_status="definitivo",
        publicavel=True,
        motivo_nao_publicavel=None,
        regra_prova={"anula_por_erro": False, "fonte": "edital §6.1"},
        topico_confianca="alta",
        topico_evidencia="",
        origem=_origem_json(),
        documento=documento,
        hash_dedup="h" * 40,
    )
    alternativa = Alternativa(questao=questao, letra="A", texto="Certa", correta=True)
    db.add_all([questao, alternativa])
    db.commit()
    assert alternativa.questao_id == questao.id


def _dispositivo_37_caput(db: Session) -> DispositivoLegal:
    dispositivo = DispositivoLegal(
        citacao_canonica="CF/88 art. 37",
        norma="CF/1988",
        artigo="37",
        inciso=None,
        paragrafo=None,
        texto="Art. 37. A administração pública direta e indireta [...]",
        vigente=True,
        fonte_url="https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
    )
    db.add(dispositivo)
    db.commit()
    return dispositivo


def test_insere_dispositivo_legal_e_citacao(db: Session) -> None:
    dispositivo = _dispositivo_37_caput(db)
    citacao = Citacao(
        conteudo_tipo="questao",
        conteudo_id=uuid.uuid4(),
        dispositivo=dispositivo,
        posicao=1,
    )
    db.add(citacao)
    db.commit()

    assert isinstance(dispositivo.id, uuid.UUID)
    assert dispositivo.atualizado_em.tzinfo is not None
    assert citacao.dispositivo_id == dispositivo.id


def test_citacao_canonica_e_unica(db: Session) -> None:
    _dispositivo_37_caput(db)
    db.add(
        DispositivoLegal(
            citacao_canonica="CF/88 art. 37",
            norma="CF/1988",
            artigo="37",
            texto="outra redação, mesma citação — não pode duplicar",
            vigente=True,
            fonte_url="https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_conteudo_tipo_da_citacao_restrito(db: Session) -> None:
    dispositivo = _dispositivo_37_caput(db)
    db.add(
        Citacao(conteudo_tipo="xx", conteudo_id=uuid.uuid4(), dispositivo=dispositivo, posicao=1)
    )
    with pytest.raises(IntegrityError):
        db.commit()


def _topico_improbidade(db: Session) -> Topico:
    topico = Topico(
        materia="direito-administrativo",
        nome="Improbidade administrativa",
        slug="dir-adm-06-improbidade-administrativa",
    )
    db.add(topico)
    db.commit()
    return topico


def test_insere_dossie_topico(db: Session) -> None:
    """Passo 3 da fundação jurídica: `dossie_topico` grava conteúdo, fontes e log de buscas."""
    topico = _topico_improbidade(db)
    dossie = DossieTopico(
        topico=topico,
        versao=1,
        gerado_em=datetime.now(UTC),
        conteudo="Art. 1º, § 1º da Lei 8.429/1992 exige dolo [F1].",
        fontes=[
            {
                "id": "F1",
                "norma": "lei-8429-1992",
                "artigo": "1",
                "inciso": None,
                "paragrafo": "1",
                "citacao_canonica": "Lei 8.429/1992 art. 1 § 1º",
                "url": "https://www.planalto.gov.br/ccivil_03/leis/l8429.htm",
                "trecho": "§ 1º Consideram-se atos de improbidade [...]",
                "tipo": "norma",
                "vigente": True,
                "redacao_de": None,
            }
        ],
        bibliografia=[],
        log_buscas=[
            {
                "n": 1,
                "consulta": "art. 1 da Lei 8.429/1992",
                "ferramenta": "extrair_artigo (offline)",
                "resultado": "aberta: trecho encontrado",
                "data": "2026-09-19",
            }
        ],
        validado_em=None,
        substituido_por=None,
    )
    db.add(dossie)
    db.commit()

    assert isinstance(dossie.id, uuid.UUID)
    assert dossie.topico_id == topico.id
    assert dossie.fontes[0]["citacao_canonica"] == "Lei 8.429/1992 art. 1 § 1º"


def test_versao_do_dossie_topico_e_unica_por_topico(db: Session) -> None:
    """Duas linhas com o mesmo `(topico_id, versao)` não podem coexistir."""
    topico = _topico_improbidade(db)
    db.add(
        DossieTopico(
            topico=topico,
            versao=1,
            gerado_em=datetime.now(UTC),
            conteudo="v1",
            fontes=[],
            bibliografia=[],
            log_buscas=[],
        )
    )
    db.commit()
    db.add(
        DossieTopico(
            topico=topico,
            versao=1,
            gerado_em=datetime.now(UTC),
            conteudo="v1 de novo",
            fontes=[],
            bibliografia=[],
            log_buscas=[],
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
