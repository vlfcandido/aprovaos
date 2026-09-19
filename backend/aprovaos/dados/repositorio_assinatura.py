"""Repositório de assinatura: cria a pendente, aplica o webhook e cancela (fatia 12, RF-22).

O que é: `assinatura_do_usuario`, `tier_do_usuario` (o tier efetivo, com `"free"` quando não há
assinatura nenhuma), `criar_ou_atualizar_pendente` (grava a assinatura recém-criada no gateway,
**antes** da confirmação), `aplicar_evento` (grava o webhook cru em `evento_cobranca` e, quando o
evento é reconhecido, atualiza `assinatura`) e `cancelar_assinatura` (marca o cancelamento local —
a rota já chamou `GatewayPagamento.cancelar` antes). Como os outros repositórios: funções soltas
recebendo `Session` como primeiro parâmetro, fazem `add`/`flush`; o `commit` é sempre da rota.
Quando ler: ao mexer em `/assinar`, `/webhooks/pagamento` ou `/assinatura/cancelar`.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Assinatura, EventoCobranca, Usuario
from aprovaos.dominio.assinatura import Periodicidade, Tier, calcular_fim_do_periodo, tier_efetivo
from aprovaos.pagamento.gateway import EventoPagamento

#: Reaproveita o vocabulário fechado de `dominio.assinatura.StatusAssinatura` para "ainda não
#: confirmada pelo webhook": `tier_efetivo("expirada", ...)` sempre devolve `"free"`, qualquer que
#: seja `fim` — exatamente o que uma assinatura recém-criada, mas não paga, deve valer. Evita
#: inventar um quinto status só para este intervalo (do clique em "assinar" até o webhook chegar).
STATUS_PENDENTE = "expirada"

#: Único gateway hoje (ADR-0025) — gravado em `assinatura.gateway`/`evento_cobranca.gateway`.
GATEWAY = "mercado_pago"


def assinatura_do_usuario(db: Session, usuario_id: UUID) -> Assinatura | None:
    """A `Assinatura` deste usuário, se já existir (uma por usuário — `UniqueConstraint`).

    Args:
        db: sessão do request.
        usuario_id: dono da assinatura.

    Returns:
        A `Assinatura`, ou `None` se ele nunca assinou.
    """
    consulta = select(Assinatura).where(Assinatura.usuario_id == usuario_id)
    return db.scalars(consulta).first()


def tier_do_usuario(db: Session, usuario_id: UUID, hoje: date) -> Tier:
    """O tier efetivo do usuário agora — `"free"` sem assinatura nenhuma.

    Args:
        db: sessão do request.
        usuario_id: quem está sendo consultado.
        hoje: a data de referência (`dados/base.py::agora_utc().date()` na chamada real).

    Returns:
        `"free"` ou `"pro"` (`dominio.assinatura.tier_efetivo`).
    """
    assinatura = assinatura_do_usuario(db, usuario_id)
    if assinatura is None:
        return "free"
    return tier_efetivo(assinatura.status, assinatura.fim, hoje)  # type: ignore[arg-type]


def criar_ou_atualizar_pendente(
    db: Session, usuario: Usuario, periodicidade: Periodicidade, id_externo: str, agora: datetime
) -> Assinatura:
    """Grava a assinatura recém-criada no gateway, ainda não confirmada pelo webhook.

    Idempotente por usuário (`UniqueConstraint(usuario_id)`, modelo de dados §2): assinar de novo
    depois de cancelar atualiza a mesma linha, nunca cria uma segunda — `cancelada_em` volta a
    `None` (uma nova tentativa de assinatura não está mais cancelada).

    Args:
        db: sessão do request.
        usuario: quem está assinando.
        periodicidade: `"mensal"` ou `"anual"` (ADR-0015).
        id_externo: o `id` da assinatura devolvido por `GatewayPagamento.criar_assinatura`.
        agora: instante da criação (`dados/base.py::agora_utc`) — vira `assinatura.inicio` e a
            base de `assinatura.fim` (`calcular_fim_do_periodo`).

    Returns:
        A `Assinatura` (nova ou atualizada), com `status=STATUS_PENDENTE` e `tier="free"` — só o
        webhook (`aplicar_evento`) a faz virar Pro.
    """
    fim = calcular_fim_do_periodo(periodicidade, agora.date())
    assinatura = assinatura_do_usuario(db, usuario.id)
    if assinatura is None:
        assinatura = Assinatura(
            usuario_id=usuario.id,
            tier="free",
            periodicidade=periodicidade,
            status=STATUS_PENDENTE,
            inicio=agora,
            fim=fim,
            gateway=GATEWAY,
            id_externo=id_externo,
        )
        db.add(assinatura)
    else:
        assinatura.tier = "free"
        assinatura.periodicidade = periodicidade
        assinatura.status = STATUS_PENDENTE
        assinatura.inicio = agora
        assinatura.fim = fim
        assinatura.gateway = GATEWAY
        assinatura.id_externo = id_externo
        assinatura.cancelada_em = None
    db.flush()
    return assinatura


#: `evento_cobranca.tipo` gravado quando `GatewayPagamento.ler_evento` devolveu `None` — a
#: assinatura HMAC conferiu, mas o evento não é um dos dois que esta fatia processa (ex.: uma
#: notificação de pagamento avulso). Grava mesmo assim (auditoria), sem tocar em `assinatura`.
TIPO_NAO_RECONHECIDO = "nao_reconhecido"


def _id_externo_do_payload_bruto(payload: dict[str, object]) -> str:
    """Extrai `payload["data"]["id"]` defensivamente, para o evento não reconhecido ter uma id.

    Vira `evento_cobranca.id_externo`; fica `""` se a forma do payload vier inesperada.
    """
    dados = payload.get("data")
    if isinstance(dados, dict):
        return str(dados.get("id", ""))
    return ""


def aplicar_evento(
    db: Session, evento: EventoPagamento | None, payload: dict[str, object], agora: datetime
) -> EventoCobranca:
    """Grava o webhook cru (auditoria) e, se reconhecido, atualiza a assinatura correspondente.

    A gravação em `evento_cobranca` acontece **sempre** — mesmo quando `evento` é `None`
    (assinatura válida, mas tipo que esta fatia não processa, `TIPO_NAO_RECONHECIDO`) ou quando
    nenhuma `Assinatura` tem o `id_externo` do evento (defensivo — não deveria acontecer, mas a
    auditoria não pode depender disso) — "dinheiro exige rastro" (plano §3).

    Args:
        db: sessão do request.
        evento: o `EventoPagamento` já validado e traduzido (`GatewayPagamento.ler_evento`), ou
            `None` quando a assinatura conferiu mas o tipo não é reconhecido.
        payload: o corpo cru do webhook, decodificado, para `evento_cobranca.payload`.
        agora: instante do processamento (`dados/base.py::agora_utc`).

    Returns:
        O `EventoCobranca` gravado, já com `processado_em` preenchido.
    """
    gateway = evento.gateway if evento is not None else GATEWAY
    tipo = evento.tipo if evento is not None else TIPO_NAO_RECONHECIDO
    id_externo = evento.id_externo if evento is not None else _id_externo_do_payload_bruto(payload)

    registro = EventoCobranca(
        gateway=gateway, id_externo=id_externo, tipo=tipo, payload=payload, recebido_em=agora
    )
    db.add(registro)

    if evento is not None:
        consulta = select(Assinatura).where(Assinatura.id_externo == evento.id_externo)
        assinatura = db.scalars(consulta).first()
        if assinatura is not None:
            if evento.tipo == "assinatura_autorizada":
                assinatura.tier = "pro"
                assinatura.status = "ativa"
            elif evento.tipo == "assinatura_cancelada":
                assinatura.status = "cancelada"
                assinatura.cancelada_em = agora

    registro.processado_em = agora
    db.flush()
    return registro


def cancelar_assinatura(db: Session, assinatura: Assinatura, agora: datetime) -> None:
    """Marca o cancelamento local (a rota já chamou `GatewayPagamento.cancelar` antes).

    Não mexe em `fim`: o Pro continua valendo até lá (`tier_efetivo`) — cancelar em um clique
    nunca devolve o que já foi pago.

    Args:
        db: sessão do request.
        assinatura: a assinatura do usuário (`assinatura_do_usuario`).
        agora: instante do cancelamento (`dados/base.py::agora_utc`).
    """
    assinatura.status = "cancelada"
    assinatura.cancelada_em = agora
    db.flush()
