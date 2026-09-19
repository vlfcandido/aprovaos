# O que é: testes de `dados/repositorio_diagnostico.py` — `topicos_do_diagnostico` (tópico sem
# nenhuma questão publicável marcado `tem_questao=False`, nunca fingindo cobertura) e
# `respostas_diagnostico` (só os `evento_estudo` marcados `dados.diagnostico=True`, na ordem em
# que ocorreram). Quando ler: ao ligar `api/diagnostico.py`.
from uuid import UUID, uuid4

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
)
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dados.repositorio_diagnostico import respostas_diagnostico, topicos_do_diagnostico
from aprovaos.dados.repositorio_questao import salvar_questoes
from aprovaos.dominio.conta import DadosCadastro
from aprovaos.dominio.questao import Origem, QuestaoCurada, RegraProva, hash_dedup


def _documento(db: Session, hash_: str) -> Documento:
    documento = Documento(
        tipo="prova", hash=hash_, caminho=f"{hash_}.pdf", baixado_em=agora_utc(), metadados={}
    )
    db.add(documento)
    db.flush()
    return documento


def _edital_com_dois_topicos(db: Session, tenant_id: UUID) -> tuple[Edital, Topico, Topico]:
    com_questao = Topico(materia="Direito Administrativo", nome="Poderes", slug=f"a-{uuid4().hex}")
    sem_questao = Topico(materia="Língua Portuguesa", nome="Crase", slug=f"b-{uuid4().hex}")
    documento_edital = _documento(db, f"edital-{uuid4().hex}")
    concurso = Concurso(tenant_id=tenant_id, orgao="TJ-PR", cargo="Técnico", banca="AOCP")
    edital = Edital(concurso=concurso, versao=1, documento=documento_edital)
    db.add_all([com_questao, sem_questao, concurso, edital])
    db.flush()
    db.add_all(
        [
            TopicoEdital(edital=edital, topico=com_questao, ordem=1, texto_original="1. Poderes."),
            TopicoEdital(edital=edital, topico=sem_questao, ordem=2, texto_original="2. Crase."),
        ]
    )
    db.flush()
    return edital, com_questao, sem_questao


def _questao(topico: Topico, documento_id: UUID, numero: int) -> QuestaoCurada:
    origem = Origem(
        banca="cebraspe",
        orgao="TJ-PR",
        cargo="Técnico",
        ano=2025,
        numero_item=numero,
        tipo_caderno=None,
        url_prova="https://cdn.cebraspe.org.br/prova.pdf",
        documento_id=str(documento_id),
    )
    enunciado = f"Enunciado {numero} sobre {topico.nome}."
    return QuestaoCurada(
        banca="cebraspe",
        numero_item=numero,
        comando="Julgue o item.",
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado=enunciado,
        gabarito_preliminar=None,
        gabarito="C",
        gabarito_status="definitivo",
        publicavel=True,
        motivo_nao_publicavel=None,
        regra_prova=RegraProva(anula_por_erro=True, fonte="instrução do caderno"),
        topico_slug=topico.slug,
        topico_confianca="alta",
        topico_evidencia="evidência",
        origem=origem,
        hash_dedup=hash_dedup(enunciado),
    )


def test_topicos_do_diagnostico_marca_tem_questao_conforme_a_base(db: Session) -> None:
    tenant_id = criar_conta(db, DadosCadastro(email="h@exemplo.com", senha="12345678")).tenant_id
    edital, com_questao, sem_questao = _edital_com_dois_topicos(db, tenant_id)
    documento_prova = _documento(db, f"prova-{uuid4().hex}")
    salvar_questoes(db, [_questao(com_questao, documento_prova.id, 1)])
    db.commit()

    topicos = {t.topico_id: t for t in topicos_do_diagnostico(db, edital.id)}
    assert topicos[com_questao.id].tem_questao is True
    assert topicos[sem_questao.id].tem_questao is False
    assert topicos[sem_questao.id].materia == "Língua Portuguesa"


def test_respostas_diagnostico_so_pega_eventos_marcados(db: Session) -> None:
    usuario = criar_conta(db, DadosCadastro(email="i@exemplo.com", senha="12345678"))
    edital, com_questao, _sem_questao = _edital_com_dois_topicos(db, usuario.tenant_id)
    documento_prova = _documento(db, f"prova-{uuid4().hex}")
    salvar_questoes(
        db,
        [
            _questao(com_questao, documento_prova.id, 1),
            _questao(com_questao, documento_prova.id, 2),
        ],
    )
    db.commit()
    questoes = list(db.scalars(select(Questao).where(Questao.topico_id == com_questao.id)))
    db.add(
        EventoEstudo(
            usuario_id=usuario.id,
            ocorrido_em=agora_utc(),
            tipo="resposta",
            questao_id=questoes[0].id,
            acertou=True,
            resposta="C",
            confianca_declarada="certeza",
            dados={"diagnostico": True},
        )
    )
    db.add(
        EventoEstudo(
            usuario_id=usuario.id,
            ocorrido_em=agora_utc(),
            tipo="resposta",
            questao_id=questoes[1].id,
            acertou=False,
            resposta="E",
            confianca_declarada="duvida",
            dados=None,  # resposta comum, fora do diagnóstico — não deve entrar
        )
    )
    db.commit()

    respostas = respostas_diagnostico(db, usuario.id, edital.id)
    assert len(respostas) == 1
    assert respostas[0].topico_id == com_questao.id
    assert respostas[0].acertou is True
    assert respostas[0].confianca == "certeza"
