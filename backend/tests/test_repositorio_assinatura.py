# O que é: testes red-first do repositório de assinatura (fatia 12, RF-22) — criar a pendente
# (Ruling 46: ainda não vale como Pro), aplicar o webhook (autorizada/cancelada) e cancelar em um
# clique. Quando ler: ao mexer em `dados/repositorio_assinatura.py`.
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Assinatura, EventoCobranca, Usuario
from aprovaos.dados.repositorio_assinatura import (
    aplicar_evento,
    assinatura_do_usuario,
    cancelar_assinatura,
    criar_ou_atualizar_pendente,
    tier_do_usuario,
)
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dominio.conta import DadosCadastro
from aprovaos.pagamento.gateway import EventoPagamento


def _usuario(db: Session, email: str = "linda@exemplo.com") -> Usuario:
    return criar_conta(db, DadosCadastro(email=email, senha="12345678"))


def test_sem_assinatura_o_tier_e_free(db: Session) -> None:
    usuario = _usuario(db)
    assert tier_do_usuario(db, usuario.id, date(2026, 9, 19)) == "free"
    assert assinatura_do_usuario(db, usuario.id) is None


def test_criar_pendente_nao_vira_pro_antes_do_webhook(db: Session) -> None:
    usuario = _usuario(db)
    agora = agora_utc()
    assinatura = criar_ou_atualizar_pendente(db, usuario, "mensal", "preap-1", agora)
    db.commit()

    assert assinatura.id_externo == "preap-1"
    assert assinatura.periodicidade == "mensal"
    assert tier_do_usuario(db, usuario.id, agora.date()) == "free"


def test_aplicar_evento_autorizado_vira_pro_e_grava_o_webhook(db: Session) -> None:
    usuario = _usuario(db)
    agora = agora_utc()
    criar_ou_atualizar_pendente(db, usuario, "mensal", "preap-1", agora)
    db.commit()

    evento = EventoPagamento(
        tipo="assinatura_autorizada", id_externo="preap-1", gateway="mercado_pago"
    )
    registro = aplicar_evento(db, evento, {"id": 1, "type": "subscription_preapproval"}, agora)
    db.commit()

    assinatura = assinatura_do_usuario(db, usuario.id)
    assert assinatura is not None
    assert assinatura.status == "ativa"
    assert assinatura.tier == "pro"
    assert tier_do_usuario(db, usuario.id, agora.date()) == "pro"

    grafado = db.scalars(select(EventoCobranca)).one()
    assert grafado.id == registro.id
    assert grafado.processado_em is not None
    assert grafado.payload["type"] == "subscription_preapproval"


def test_aplicar_evento_cancelado_marca_cancelada(db: Session) -> None:
    usuario = _usuario(db)
    agora = agora_utc()
    criar_ou_atualizar_pendente(db, usuario, "mensal", "preap-1", agora)
    aplicar_evento(
        db,
        EventoPagamento(tipo="assinatura_autorizada", id_externo="preap-1", gateway="mercado_pago"),
        {},
        agora,
    )
    db.commit()

    aplicar_evento(
        db,
        EventoPagamento(tipo="assinatura_cancelada", id_externo="preap-1", gateway="mercado_pago"),
        {},
        agora,
    )
    db.commit()

    assinatura = assinatura_do_usuario(db, usuario.id)
    assert assinatura is not None
    assert assinatura.status == "cancelada"
    assert assinatura.cancelada_em == agora


def test_aplicar_evento_sem_assinatura_correspondente_so_grava_o_webhook(db: Session) -> None:
    evento = EventoPagamento(
        tipo="assinatura_autorizada", id_externo="preap-desconhecido", gateway="mercado_pago"
    )
    registro = aplicar_evento(db, evento, {}, agora_utc())
    db.commit()
    assert registro.processado_em is not None


def test_aplicar_evento_none_grava_evento_nao_reconhecido(db: Session) -> None:
    payload = {"id": 1, "type": "payment", "data": {"id": "pay-1"}}
    registro = aplicar_evento(db, None, payload, agora_utc())
    db.commit()
    assert registro.tipo == "nao_reconhecido"
    assert registro.id_externo == "pay-1"
    assert registro.processado_em is not None


def test_cancelar_assinatura_mantem_pro_ate_o_fim_do_periodo(db: Session) -> None:
    usuario = _usuario(db)
    agora = agora_utc()
    criar_ou_atualizar_pendente(db, usuario, "mensal", "preap-1", agora)
    aplicar_evento(
        db,
        EventoPagamento(tipo="assinatura_autorizada", id_externo="preap-1", gateway="mercado_pago"),
        {},
        agora,
    )
    db.commit()

    assinatura = assinatura_do_usuario(db, usuario.id)
    assert assinatura is not None
    cancelar_assinatura(db, assinatura, agora)
    db.commit()

    assert assinatura.status == "cancelada"
    assert assinatura.cancelada_em == agora
    # ainda dentro do período pago (fim = agora + 1 mês)
    assert tier_do_usuario(db, usuario.id, agora.date()) == "pro"
    depois_do_fim = assinatura.fim + timedelta(days=1)
    assert tier_do_usuario(db, usuario.id, depois_do_fim) == "free"


def test_assinar_de_novo_depois_de_cancelar_atualiza_a_mesma_linha(db: Session) -> None:
    usuario = _usuario(db)
    agora = agora_utc()
    criar_ou_atualizar_pendente(db, usuario, "mensal", "preap-1", agora)
    aplicar_evento(
        db,
        EventoPagamento(tipo="assinatura_autorizada", id_externo="preap-1", gateway="mercado_pago"),
        {},
        agora,
    )
    db.commit()
    assinatura = assinatura_do_usuario(db, usuario.id)
    assert assinatura is not None
    cancelar_assinatura(db, assinatura, agora)
    db.commit()

    nova = criar_ou_atualizar_pendente(db, usuario, "anual", "preap-2", agora)
    db.commit()

    assert nova.id == assinatura.id  # mesma linha, não uma segunda (UniqueConstraint usuario_id)
    assert nova.id_externo == "preap-2"
    assert nova.cancelada_em is None
    assert db.scalar(select(Assinatura.id).where(Assinatura.usuario_id == usuario.id)) == nova.id
