# O que é: testes de `dados/repositorio_fio_memoria.py` — a agregação por tópico
# (`estatisticas_topicos_vistos`) e a contagem de posição no bloco (`quantidade_no_bloco`).
# Quando ler: ao mexer nessas duas consultas ou ao investigar por que um tópico não entrou na
# estatística (`tipo` diferente de `"resposta"`, edital errado, ou nenhuma resposta ainda).
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import (
    Concurso,
    Documento,
    Edital,
    EventoEstudo,
    Questao,
    Topico,
    TopicoEdital,
    Usuario,
)
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dados.repositorio_fio_memoria import (
    estatisticas_topicos_vistos,
    quantidade_no_bloco,
)
from aprovaos.dados.repositorio_questao import salvar_questoes
from aprovaos.dominio.conta import DadosCadastro
from aprovaos.dominio.questao import Origem, QuestaoCurada, RegraProva, hash_dedup


def _usuario(db: Session, email: str) -> Usuario:
    return criar_conta(db, DadosCadastro(email=email, senha="12345678"))


def _documento(db: Session, hash_: str) -> Documento:
    documento = Documento(
        tipo="prova", hash=hash_, caminho=f"{hash_}.pdf", baixado_em=agora_utc(), metadados={}
    )
    db.add(documento)
    db.flush()
    return documento


def _topico(db: Session, slug: str, *, materia: str = "DIREITO CIVIL", nome: str = "") -> Topico:
    topico = Topico(materia=materia, nome=nome or slug, slug=slug)
    db.add(topico)
    db.flush()
    return topico


def _edital_com_topicos(db: Session, tenant_id: UUID, topicos: list[Topico]) -> Edital:
    documento = _documento(db, f"edital-{topicos[0].slug}")
    concurso = Concurso(tenant_id=tenant_id, orgao="TJ-PA", cargo="Analista", banca="cebraspe")
    edital = Edital(concurso=concurso, versao=1, documento=documento)
    db.add_all([concurso, edital])
    db.flush()
    for ordem, topico in enumerate(topicos, start=1):
        db.add(
            TopicoEdital(
                edital=edital, topico=topico, ordem=ordem, texto_original=f"{ordem}. {topico.nome}"
            )
        )
    db.flush()
    return edital


def _questao(db: Session, topico: Topico, documento_id: UUID, *, numero_item: int) -> Questao:
    origem = Origem(
        banca="cebraspe",
        orgao="TJ-PA",
        cargo="Analista",
        ano=2025,
        numero_item=numero_item,
        tipo_caderno=None,
        url_prova="https://cdn.cebraspe.org.br/prova.pdf",
        documento_id=str(documento_id),
    )
    curada = QuestaoCurada(
        banca="cebraspe",
        numero_item=numero_item,
        comando="Julgue o item a seguir.",
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado=f"Enunciado {numero_item}.",
        gabarito_preliminar=None,
        gabarito="C",
        gabarito_status="definitivo",
        publicavel=True,
        motivo_nao_publicavel=None,
        regra_prova=RegraProva(anula_por_erro=True, fonte="instrução do caderno"),
        topico_slug=topico.slug,
        topico_confianca="alta",
        topico_evidencia="fixture de teste",
        origem=origem,
        hash_dedup=hash_dedup(f"{numero_item}-{topico.slug}"),
    )
    salvar_questoes(db, [curada])
    db.flush()
    return db.scalars(select(Questao).where(Questao.hash_dedup == curada.hash_dedup)).one()


def _evento(
    db: Session,
    usuario: Usuario,
    questao: Questao,
    *,
    acertou: bool,
    ha_dias: int,
    dados: dict[str, object] | None = None,
) -> EventoEstudo:
    evento = EventoEstudo(
        usuario_id=usuario.id,
        ocorrido_em=agora_utc() - timedelta(days=ha_dias),
        tipo="resposta",
        questao_id=questao.id,
        acertou=acertou,
        resposta="C" if acertou else "E",
        tempo_ms=100,
        confianca_declarada="certeza",
        dados=dados,
    )
    db.add(evento)
    db.flush()
    return evento


def test_sem_resposta_nao_ha_estatistica(db: Session) -> None:
    usuario = _usuario(db, "a@exemplo.com")
    topico = _topico(db, "dir-civ-01")
    edital = _edital_com_topicos(db, usuario.tenant_id, [topico])
    assert estatisticas_topicos_vistos(db, usuario.id, edital.id) == []


def test_agrega_ultima_visita_total_e_erros_por_topico(db: Session) -> None:
    usuario = _usuario(db, "b@exemplo.com")
    documento = _documento(db, "doc-1")
    topico_a = _topico(db, "dir-civ-01", nome="Prescrição")
    topico_b = _topico(db, "dir-adm-01", materia="DIREITO ADMINISTRATIVO", nome="Licitações")
    edital = _edital_com_topicos(db, usuario.tenant_id, [topico_a, topico_b])

    questao_a1 = _questao(db, topico_a, documento.id, numero_item=1)
    questao_a2 = _questao(db, topico_a, documento.id, numero_item=2)
    questao_a3 = _questao(db, topico_a, documento.id, numero_item=3)
    questao_b1 = _questao(db, topico_b, documento.id, numero_item=4)

    _evento(db, usuario, questao_a1, acertou=False, ha_dias=6)
    _evento(db, usuario, questao_a2, acertou=False, ha_dias=3)
    _evento(db, usuario, questao_a3, acertou=True, ha_dias=1)
    _evento(db, usuario, questao_b1, acertou=True, ha_dias=90)
    db.commit()

    estatisticas = {e.topico_id: e for e in estatisticas_topicos_vistos(db, usuario.id, edital.id)}
    assert set(estatisticas) == {topico_a.id, topico_b.id}

    do_a = estatisticas[topico_a.id]
    assert do_a.materia == "DIREITO CIVIL"
    assert do_a.total_respostas == 3
    assert do_a.erros == 2
    assert do_a.ultimo_erro_em is not None
    # A resposta errada mais recente foi há 3 dias (a de 1 dia atrás acertou).
    assert (agora_utc() - do_a.ultimo_erro_em).days == 3
    # A última visita é a mais recente das três (1 dia atrás).
    assert (agora_utc() - do_a.ultima_visita).days == 1

    do_b = estatisticas[topico_b.id]
    assert do_b.total_respostas == 1
    assert do_b.erros == 0
    assert do_b.ultimo_erro_em is None


def test_evento_de_outro_tipo_nao_conta(db: Session) -> None:
    usuario = _usuario(db, "c@exemplo.com")
    documento = _documento(db, "doc-2")
    topico = _topico(db, "dir-civ-02")
    edital = _edital_com_topicos(db, usuario.tenant_id, [topico])
    questao = _questao(db, topico, documento.id, numero_item=1)
    evento = EventoEstudo(
        usuario_id=usuario.id,
        ocorrido_em=agora_utc(),
        tipo="reporte",
        questao_id=questao.id,
    )
    db.add(evento)
    db.commit()
    assert estatisticas_topicos_vistos(db, usuario.id, edital.id) == []


def test_quantidade_no_bloco_conta_so_os_eventos_marcados_deste_topico(db: Session) -> None:
    usuario = _usuario(db, "d@exemplo.com")
    documento = _documento(db, "doc-3")
    topico_atual = _topico(db, "dir-civ-03")
    topico_outro = _topico(db, "dir-adm-02")
    _edital_com_topicos(db, usuario.tenant_id, [topico_atual, topico_outro])
    questao_nativa = _questao(db, topico_atual, documento.id, numero_item=1)
    questao_intercalada = _questao(db, topico_outro, documento.id, numero_item=2)
    questao_de_outro_bloco = _questao(db, topico_outro, documento.id, numero_item=3)

    assert quantidade_no_bloco(db, usuario.id, topico_atual.id) == 0

    _evento(
        db,
        usuario,
        questao_nativa,
        acertou=True,
        ha_dias=0,
        dados={"bloco_topico_id": str(topico_atual.id)},
    )
    _evento(
        db,
        usuario,
        questao_intercalada,
        acertou=False,
        ha_dias=0,
        dados={"bloco_topico_id": str(topico_atual.id), "fio_motivo": "m"},
    )
    # Resposta de outro bloco (outro tópico como âncora) não conta aqui.
    _evento(
        db,
        usuario,
        questao_de_outro_bloco,
        acertou=True,
        ha_dias=0,
        dados={"bloco_topico_id": str(topico_outro.id)},
    )
    db.commit()

    assert quantidade_no_bloco(db, usuario.id, topico_atual.id) == 2
    assert quantidade_no_bloco(db, usuario.id, topico_outro.id) == 1
