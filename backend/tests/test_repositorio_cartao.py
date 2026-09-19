# O que é: testes do passo 2 da V4 — `dados/repositorio_cartao.py` (o erro faz nascer o cartão,
# idempotência por usuário/questão, agenda de vencidos na ordem do FSRS e a revisão que grava
# `evento_estudo` e atualiza o estado juntos). Quando ler: ao mexer no repositório de cartões.
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Cartao, Documento, EventoEstudo, Questao, Topico, Usuario
from aprovaos.dados.repositorio_cartao import (
    ORIGEM_AUTO_ERRO,
    buscar_cartao_da_questao,
    cartoes_vencidos,
    registrar_erro,
    revisar_cartao,
)
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dominio.conta import DadosCadastro


def _usuario(db: Session, email: str = "linda@exemplo.com") -> Usuario:
    return criar_conta(db, DadosCadastro(email=email, senha="12345678"))


def _topico(db: Session, slug: str = "dir-civ-01-prescricao") -> Topico:
    topico = Topico(materia="DIREITO CIVIL", nome="Prescrição", slug=slug)
    db.add(topico)
    db.flush()
    return topico


def _questao(db: Session, topico: Topico | None, *, gabarito: str | None = "C") -> Questao:
    documento = Documento(
        tipo="prova",
        hash=f"h-{id(topico)}-{gabarito}",
        caminho="p.pdf",
        baixado_em=agora_utc(),
        metadados={},
    )
    db.add(documento)
    db.flush()
    questao = Questao(
        adapter="concursos",
        banca="cebraspe",
        tipo_item="certo_errado",
        comando="Julgue o item a seguir.",
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado="O prazo prescricional é de 5 anos.",
        gabarito_preliminar=None,
        gabarito=gabarito,
        gabarito_status="definitivo" if gabarito else "sem_gabarito",
        publicavel=gabarito is not None,
        motivo_nao_publicavel=None,
        regra_prova={"anula_por_erro": True, "fonte": "instrução do caderno"},
        topico=topico,
        topico_confianca="alta" if topico else "baixa",
        topico_evidencia="menciona prescrição",
        origem={
            "banca": "cebraspe",
            "orgao": "TJ-PA",
            "cargo": "Analista",
            "ano": 2025,
            "numero_item": 1,
            "tipo_caderno": None,
            "url_prova": "https://cdn.cebraspe.org.br/prova.pdf",
            "documento_id": str(documento.id),
        },
        documento=documento,
        hash_dedup=f"hash-{id(topico)}-{gabarito}",
    )
    db.add(questao)
    db.flush()
    return questao


def test_registrar_erro_cria_cartao_auto_erro(db: Session) -> None:
    usuario = _usuario(db)
    topico = _topico(db)
    questao = _questao(db, topico)
    agora = agora_utc()

    cartao = registrar_erro(db, usuario, questao, "duvida", agora)

    assert cartao is not None
    assert cartao.origem == ORIGEM_AUTO_ERRO
    assert cartao.usuario_id == usuario.id
    assert cartao.questao_id == questao.id
    assert cartao.topico_id == topico.id
    assert cartao.reps == 1
    assert cartao.lapses == 0
    assert cartao.due >= agora
    assert "prescricional" in cartao.frente
    assert "C" in cartao.verso


def test_registrar_erro_nao_duplica_cartao_da_mesma_questao(db: Session) -> None:
    usuario = _usuario(db)
    topico = _topico(db)
    questao = _questao(db, topico)
    agora = agora_utc()

    primeiro = registrar_erro(db, usuario, questao, "duvida", agora)
    assert primeiro is not None
    db.commit()

    segundo = registrar_erro(db, usuario, questao, "duvida", agora + timedelta(hours=1))
    assert segundo is not None
    db.commit()

    assert primeiro.id == segundo.id
    total = db.scalar(select(func.count(Cartao.id)))
    assert total == 1


def test_registrar_erro_sem_topico_nao_cria_cartao(db: Session) -> None:
    usuario = _usuario(db)
    questao = _questao(db, None)

    cartao = registrar_erro(db, usuario, questao, "certeza", agora_utc())

    assert cartao is None
    assert buscar_cartao_da_questao(db, usuario.id, questao.id) is None


def test_cartoes_vencidos_ordena_por_due(db: Session) -> None:
    usuario = _usuario(db)
    topico = _topico(db)
    agora = agora_utc()

    questao_1 = _questao(db, topico, gabarito="C")
    questao_2 = _questao(db, topico, gabarito="E")
    cartao_1 = registrar_erro(db, usuario, questao_1, "duvida", agora - timedelta(days=2))
    cartao_2 = registrar_erro(db, usuario, questao_2, "certeza", agora - timedelta(days=1))
    assert cartao_1 is not None and cartao_2 is not None
    db.commit()

    # os dois já nasceram vencidos (a agenda inicial do FSRS é minutos depois do erro); o cartão
    # criado há mais tempo (`cartao_1`) tem `due` mais antigo e vem primeiro.
    vencidos = cartoes_vencidos(db, usuario.id, agora)

    assert [c.id for c in vencidos] == [cartao_1.id, cartao_2.id]
    assert vencidos[0].due <= vencidos[1].due


def test_cartao_nao_vencido_fica_fora_da_agenda(db: Session) -> None:
    usuario = _usuario(db)
    topico = _topico(db)
    questao = _questao(db, topico)
    agora = agora_utc()
    registrar_erro(db, usuario, questao, "duvida", agora)
    db.commit()

    # daqui a uma semana o cartão criado agora já teria vencido; "agora - 1 dia" é antes de ele
    # sequer nascer, então nunca está vencido.
    vencidos = cartoes_vencidos(db, usuario.id, agora - timedelta(days=1))

    assert vencidos == []


def test_revisar_cartao_grava_evento_e_atualiza_estado(db: Session) -> None:
    usuario = _usuario(db)
    topico = _topico(db)
    questao = _questao(db, topico)
    agora = agora_utc()
    cartao = registrar_erro(db, usuario, questao, "duvida", agora)
    assert cartao is not None
    db.commit()
    due_antes = cartao.due
    reps_antes = cartao.reps

    evento = revisar_cartao(
        db,
        usuario,
        cartao,
        acertou=True,
        resposta="C",
        confianca="certeza",
        tempo_ms=3000,
        agora=agora + timedelta(minutes=15),
    )
    db.commit()

    assert evento.tipo == "revisao_cartao"
    assert evento.cartao_id == cartao.id
    assert evento.questao_id == questao.id
    assert evento.acertou is True
    linha = db.get(Cartao, cartao.id)
    assert linha is not None
    assert linha.reps == reps_antes + 1
    assert linha.due != due_antes


def test_revisar_cartao_registra_evento_mesmo_quando_erra_de_novo(db: Session) -> None:
    usuario = _usuario(db)
    topico = _topico(db)
    questao = _questao(db, topico)
    agora = agora_utc()
    cartao = registrar_erro(db, usuario, questao, "duvida", agora)
    assert cartao is not None
    db.commit()

    revisar_cartao(
        db,
        usuario,
        cartao,
        acertou=False,
        resposta="E",
        confianca="duvida",
        tempo_ms=1000,
        agora=agora + timedelta(minutes=5),
    )
    db.commit()

    eventos = db.scalars(select(EventoEstudo).where(EventoEstudo.tipo == "revisao_cartao")).all()
    assert len(eventos) == 1
    assert eventos[0].acertou is False
