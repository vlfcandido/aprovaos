# O que é: testes do passo 12 da V3 — o comando `curar` (motor/curar.py), que liga o coletor
# (passo 5), a classificação (passo 8), o curador (passo 9) e o repositório de questões (passo
# 11) num único `curar_documento`. Quando ler: ao mudar `curar_documento`, `_origem_base` ou a
# resolução do vocabulário/documentos a partir do banco.
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.config import Configuracoes
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Concurso, Documento, Edital, Questao, Topico, TopicoEdital, Traco
from aprovaos.dominio.edital import extrair_conteudo_programatico
from aprovaos.motor.curadoria.classificacao import (
    Classificacao,
    ItemParaClassificar,
    MotivosRejeicao,
)
from aprovaos.motor.curar import curar_documento
from aprovaos.roteador.custo import ChamadaLlm

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_MD = RAIZ / "docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md"

CAMINHO_PROVA_TJ_PA = (
    "TJ_PA_25_SERVIDOR/C15F414E0E91EF109220A73BDF53B232C4466F64770A91E715C56DCB94131F41.pdf"
)
CAMINHO_GABARITO_TJ_PA = (
    "TJ_PA_25_SERVIDOR/EF721EA56FA324A5AE5E9F7A8FD2FE4800E803E772BC6D03E0403D1B61632F72.pdf"
)
N_ITENS_TJ_PA = 70
ANULADOS_TJ_PA = 5

# Cadernos sintéticos, no mesmo espírito de `test_curador.py`: só para exercitar a lógica de
# `curar_documento` (localizar `Documento`, montar `OrigemBase`, gravar/relatar) — a segmentação
# e a leitura do gabarito em si já são cobertas contra o caderno real em `test_dominio_prova.py`,
# `test_dominio_gabarito.py` e `test_curador.py`.
_TEXTO_PROVA_SINTETICO = (
    "Acerca de direito administrativo, julgue os itens subsequentes.\n"
    "1 Primeiro item sintético para o teste de pendência.\n"
    "2 Segundo item sintético para o teste de pendência.\n"
)
# 1 entrada de gabarito para 2 itens do caderno — contagem divergente (pendente_revisao).
_TEXTO_GABARITO_DIVERGENTE = "GABARITOS OFICIAIS DEFINITIVOS\n1\nC\n"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _documento_prova(db: Session, *, caminho: str, evento: str, descricao: str) -> Documento:
    documento = Documento(
        tipo="prova",
        hash=f"prova-{uuid4().hex}",
        caminho=caminho,
        baixado_em=agora_utc(),
        metadados={
            "descricao": descricao,
            "evento": evento,
            "url_origem": f"https://cdn.cebraspe.org.br/concursos/{evento}/arquivos/prova.pdf",
        },
    )
    db.add(documento)
    db.flush()
    return documento


def _documento_gabarito(db: Session, *, caminho: str, evento: str, descricao: str) -> Documento:
    documento = Documento(
        tipo="gabarito",
        hash=f"gabarito-{uuid4().hex}",
        caminho=caminho,
        baixado_em=agora_utc(),
        metadados={
            "descricao": descricao,
            "evento": evento,
            "url_origem": f"https://cdn.cebraspe.org.br/concursos/{evento}/arquivos/gabarito.pdf",
        },
    )
    db.add(documento)
    db.flush()
    return documento


def _edital_com_vocabulario_real(db: Session) -> Edital:
    """Edital com o vocabulário real da Linda (mesmo fixture de `test_curador.py`)."""
    texto = FIXTURE_MD.read_text(encoding="utf-8")
    materias = extrair_conteudo_programatico(texto)
    documento_edital = Documento(
        tipo="edital",
        hash=f"edital-{uuid4().hex}",
        caminho="edital.pdf",
        baixado_em=agora_utc(),
        metadados={},
    )
    concurso = Concurso(tenant_id=None, orgao="TJ-PA", cargo="Analista", banca="cebraspe")
    edital = Edital(concurso=concurso, versao=1, documento=documento_edital)
    db.add_all([documento_edital, concurso, edital])
    db.flush()
    ordem = 0
    for materia in materias:
        for item in materia.topicos:
            ordem += 1
            db.add(
                TopicoEdital(
                    edital=edital,
                    topico=Topico(materia=materia.nome, nome=item.texto_original, slug=item.slug),
                    ordem=ordem,
                    texto_original=item.texto_original,
                )
            )
    db.flush()
    return edital


def _edital_vazio(db: Session) -> Edital:
    """Edital sem nenhum `TopicoEdital` — usado nos testes que não chegam a classificar."""
    documento_edital = Documento(
        tipo="edital",
        hash=f"edital-vazio-{uuid4().hex}",
        caminho="edital-vazio.pdf",
        baixado_em=agora_utc(),
        metadados={},
    )
    concurso = Concurso(tenant_id=None, orgao="TJ-PA", cargo="Analista", banca="cebraspe")
    edital = Edital(concurso=concurso, versao=1, documento=documento_edital)
    db.add_all([documento_edital, concurso, edital])
    db.flush()
    return edital


@pytest.mark.anyio
async def test_curar_grava_questoes(db: Session, config_teste: Configuracoes) -> None:
    """`curar_documento` sobre o caderno real da TJ-PA grava as 70 questões e conta certo.

    Sem `GOOGLE_API_KEY` (`config_teste` não define uma): zero chamadas de LLM, zero linhas de
    `traco` — a classificação inteira sai de `ClassificadorPorRegras`.
    """
    documento_prova = _documento_prova(
        db,
        caminho=CAMINHO_PROVA_TJ_PA,
        evento="TJ_PA_25_SERVIDOR",
        descricao="PROVA OBJETIVA – CONHECIMENTOS ESPECÍFICOS – CARGO 9",
    )
    documento_gabarito = _documento_gabarito(
        db,
        caminho=CAMINHO_GABARITO_TJ_PA,
        evento="TJ_PA_25_SERVIDOR",
        descricao="GABARITO DEFINITIVO – CONHECIMENTOS ESPECÍFICOS – CARGO 9",
    )
    edital = _edital_com_vocabulario_real(db)
    db.commit()

    relatorio = await curar_documento(
        db, config_teste, documento_prova.id, documento_gabarito.id, edital.id
    )
    db.commit()

    assert relatorio.pendente_revisao is False
    assert relatorio.total == N_ITENS_TJ_PA
    assert relatorio.anuladas == ANULADOS_TJ_PA
    assert relatorio.publicaveis > 0
    assert relatorio.sem_topico >= 0
    assert relatorio.novas == N_ITENS_TJ_PA
    assert relatorio.repetidas == 0
    assert relatorio.problemas == []
    assert db.scalar(select(func.count()).select_from(Questao)) == N_ITENS_TJ_PA
    assert db.scalar(select(func.count()).select_from(Traco)) == 0

    salvas = db.scalars(select(Questao)).all()
    origem_alguma = next(q.origem for q in salvas if q.origem is not None)
    assert origem_alguma["banca"] == "cebraspe"
    assert origem_alguma["orgao"] == "TJ-PA"
    assert origem_alguma["ano"] == 2025
    assert origem_alguma["cargo"] == "CARGO 9"
    assert origem_alguma["documento_id"] == str(documento_prova.id)


@pytest.mark.anyio
async def test_pendente_revisao_nao_grava_nada(
    db: Session, config_teste: Configuracoes, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Gabarito com uma entrada a menos que os itens do caderno → nada gravado, problema relatado.

    Sintético e determinístico (a mesma divergência que a skill `ingestao-de-provas` cobre),
    sem fabricar um PDF de banca real: `extrair_texto` — a fronteira de I/O — é trocado por um
    dublê que devolve o texto sintético a partir do conteúdo gravado em disco.
    """
    pasta = tmp_path / "provas" / "SINTETICO_24"
    pasta.mkdir(parents=True)
    (pasta / "prova.pdf").write_bytes(b"conteudo-prova-sintetica")
    (pasta / "gabarito.pdf").write_bytes(b"conteudo-gabarito-divergente")
    config = config_teste.model_copy(update={"documentos_dir": tmp_path / "provas"})

    documento_prova = _documento_prova(
        db,
        caminho="SINTETICO_24/prova.pdf",
        evento="SINTETICO_24",
        descricao="PROVA OBJETIVA – CONHECIMENTOS ESPECÍFICOS – CARGO 1",
    )
    documento_gabarito = _documento_gabarito(
        db,
        caminho="SINTETICO_24/gabarito.pdf",
        evento="SINTETICO_24",
        descricao="GABARITO DEFINITIVO – CONHECIMENTOS ESPECÍFICOS – CARGO 1",
    )
    edital = _edital_vazio(db)
    db.commit()

    def extrair_texto_falso(conteudo: bytes) -> str:
        if conteudo == b"conteudo-prova-sintetica":
            return _TEXTO_PROVA_SINTETICO
        return _TEXTO_GABARITO_DIVERGENTE

    monkeypatch.setattr("aprovaos.motor.curar.extrair_texto", extrair_texto_falso)

    relatorio = await curar_documento(
        db, config, documento_prova.id, documento_gabarito.id, edital.id
    )
    db.commit()

    assert relatorio.pendente_revisao is True
    assert relatorio.total == 0
    assert relatorio.publicaveis == 0
    assert relatorio.anuladas == 0
    assert relatorio.sem_topico == 0
    assert relatorio.novas == 0
    assert relatorio.repetidas == 0
    assert any("≠ gabarito" in problema for problema in relatorio.problemas)
    assert db.scalar(select(func.count()).select_from(Questao)) == 0
    assert db.scalar(select(func.count()).select_from(Traco)) == 0


class _ClassificadorFalso:
    """Dublê de `ClassificadorDeTopico`: devolve tudo sem tópico, mas registra `ChamadaLlm`.

    Existe para provar que `curar_documento` grava **um `traco` por chamada** quando a IA
    entra — sem rede, sem `google.*` (a fábrica real, `criar_classificador_adk`, é trocada por
    esta em `monkeypatch`).
    """

    def __init__(self, registrar_chamada: object) -> None:
        self._registrar_chamada = registrar_chamada

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[object]
    ) -> tuple[list[Classificacao], MotivosRejeicao]:
        self._registrar_chamada(  # type: ignore[operator]
            ChamadaLlm(
                agente="classificador-teste",
                modelo="modelo-falso",
                iniciado_em=datetime.now(UTC),
                duracao_ms=5,
                tokens_in=10,
                tokens_out=10,
                custo_brl=None,
                resultado="ok",
            )
        )
        classificacoes = [
            Classificacao(
                numero_item=item.numero_item,
                topico_slug=None,
                confianca="baixa",
                evidencia="dublê: sem correspondência de propósito",
                origem="ia",
            )
            for item in itens
        ]
        return classificacoes, {}


@pytest.mark.anyio
async def test_curar_registra_traco_por_chamada_de_llm(
    db: Session, config_teste: Configuracoes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com `GOOGLE_API_KEY` e teto disponível: um `traco` por lote — sem tocar a rede.

    `montar_lotes(70, 20) == [20, 20, 20, 10]`: 4 lotes, 4 linhas de `traco`, todas com
    `usuario_id is None` (comando, não rota autenticada).
    """
    documento_prova = _documento_prova(
        db,
        caminho=CAMINHO_PROVA_TJ_PA,
        evento="TJ_PA_25_SERVIDOR",
        descricao="PROVA OBJETIVA – CONHECIMENTOS ESPECÍFICOS – CARGO 9",
    )
    documento_gabarito = _documento_gabarito(
        db,
        caminho=CAMINHO_GABARITO_TJ_PA,
        evento="TJ_PA_25_SERVIDOR",
        descricao="GABARITO DEFINITIVO – CONHECIMENTOS ESPECÍFICOS – CARGO 9",
    )
    edital = _edital_com_vocabulario_real(db)
    db.commit()

    config_com_chave = config_teste.model_copy(update={"google_api_key": SecretStr("fake-key")})
    monkeypatch.setattr(
        "aprovaos.motor.curar.criar_classificador_adk",
        lambda _config, registrar_chamada: _ClassificadorFalso(registrar_chamada),
    )

    relatorio = await curar_documento(
        db, config_com_chave, documento_prova.id, documento_gabarito.id, edital.id
    )
    db.commit()

    assert relatorio.pendente_revisao is False
    assert relatorio.total == N_ITENS_TJ_PA
    tracos = db.scalars(select(Traco)).all()
    assert len(tracos) == 4
    assert all(traco.usuario_id is None for traco in tracos)
    assert all(traco.agente == "classificador-teste" for traco in tracos)


class _ClassificadorTudoNoMesmoTopico:
    """Dublê: classifica todo item num único tópico válido, confiança alta — sem rede.

    Usado só para provar `reclassificar=True`: se toda questão migrar para o mesmo tópico
    válido, dá para conferir que `atualizar_classificacao` (passo 12b) mexeu nas 70 sem duplicar
    nenhuma linha.
    """

    def __init__(self, registrar_chamada: object, slug: str) -> None:
        self._registrar_chamada = registrar_chamada
        self._slug = slug

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[object]
    ) -> tuple[list[Classificacao], MotivosRejeicao]:
        self._registrar_chamada(  # type: ignore[operator]
            ChamadaLlm(
                agente="classificador-teste",
                modelo="modelo-falso",
                iniciado_em=datetime.now(UTC),
                duracao_ms=5,
                tokens_in=10,
                tokens_out=10,
                custo_brl=None,
                resultado="ok",
            )
        )
        classificacoes = [
            Classificacao(
                numero_item=item.numero_item,
                topico_slug=self._slug,
                confianca="alta",
                evidencia="dublê: tudo no mesmo tópico, de propósito",
                origem="ia",
            )
            for item in itens
        ]
        return classificacoes, {}


@pytest.mark.anyio
async def test_curar_documento_reclassificar_atualiza_sem_duplicar(
    db: Session, config_teste: Configuracoes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`reclassificar=True`: reclassifica as 70 já gravadas, sem criar nenhuma linha nova."""
    documento_prova = _documento_prova(
        db,
        caminho=CAMINHO_PROVA_TJ_PA,
        evento="TJ_PA_25_SERVIDOR",
        descricao="PROVA OBJETIVA – CONHECIMENTOS ESPECÍFICOS – CARGO 9",
    )
    documento_gabarito = _documento_gabarito(
        db,
        caminho=CAMINHO_GABARITO_TJ_PA,
        evento="TJ_PA_25_SERVIDOR",
        descricao="GABARITO DEFINITIVO – CONHECIMENTOS ESPECÍFICOS – CARGO 9",
    )
    edital = _edital_com_vocabulario_real(db)
    db.commit()

    relatorio_inicial = await curar_documento(
        db, config_teste, documento_prova.id, documento_gabarito.id, edital.id
    )
    db.commit()
    assert relatorio_inicial.novas == N_ITENS_TJ_PA
    assert relatorio_inicial.sem_topico > 0  # por regras, boa parte fica sem tópico (medido: 57)

    slug_alvo = "dir-adm-01-principios-administracao"
    config_com_chave = config_teste.model_copy(update={"google_api_key": SecretStr("fake-key")})
    monkeypatch.setattr(
        "aprovaos.motor.curar.criar_classificador_adk",
        lambda _config, registrar_chamada: _ClassificadorTudoNoMesmoTopico(
            registrar_chamada, slug_alvo
        ),
    )

    relatorio_reclassificado = await curar_documento(
        db,
        config_com_chave,
        documento_prova.id,
        documento_gabarito.id,
        edital.id,
        reclassificar=True,
    )
    db.commit()

    assert relatorio_reclassificado.pendente_revisao is False
    assert relatorio_reclassificado.novas == 0
    assert relatorio_reclassificado.repetidas == 0
    assert relatorio_reclassificado.atualizadas == N_ITENS_TJ_PA
    assert relatorio_reclassificado.sem_topico == 0
    assert relatorio_reclassificado.publicaveis == N_ITENS_TJ_PA - ANULADOS_TJ_PA
    # nenhuma linha nova: ainda 70, não 140.
    assert db.scalar(select(func.count()).select_from(Questao)) == N_ITENS_TJ_PA

    topico = db.scalars(select(Topico).where(Topico.slug == slug_alvo)).one()
    no_topico = db.scalar(
        select(func.count()).select_from(Questao).where(Questao.topico_id == topico.id)
    )
    assert no_topico == N_ITENS_TJ_PA
