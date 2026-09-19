"""Repositório de cartões de revisão espaçada (V4, F4.3): grava o erro, agenda e revisa.

O que é: `registrar_erro` (o erro de uma questão faz nascer, ou atualiza sem duplicar, o cartão
daquela questão — `UniqueConstraint(usuario_id, questao_id)` de `Cartao`), `cartoes_vencidos`
(agenda do dia: `due <= agora`, ordenados por `due`, a própria ordem do FSRS) e `revisar_cartao`
(aplica uma revisão — grava `EventoEstudo(tipo="revisao_cartao")` **e** atualiza o estado do
cartão, as duas coisas, nunca só uma). Como os outros repositórios (`repositorio_questao.py`):
funções soltas recebendo `Session` como primeiro parâmetro, fazem `add`/`flush`; o `commit` é
sempre da rota. Quando ler: ao ligar o erro de uma questão ao nascimento do cartão, ou a rota
`/revisar`.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Cartao, EventoEstudo, Questao, Usuario
from aprovaos.dominio.revisao import Confianca, EstadoCartaoFsrs, montar_frente_verso, revisar

#: Origem gravada por `registrar_erro` — a única que esta fatia produz (`"manual"` fica para
#: quando existir uma tela de criar cartão à mão).
ORIGEM_AUTO_ERRO = "auto_erro"


def _estado_do_cartao(cartao: Cartao) -> EstadoCartaoFsrs:
    """Lê as colunas de estado FSRS de um `Cartao` já existente."""
    return EstadoCartaoFsrs(
        stability=cartao.stability,
        difficulty=cartao.difficulty,
        due=cartao.due,
        last_review=cartao.last_review,
        reps=cartao.reps,
        lapses=cartao.lapses,
        estado_fsrs=cartao.estado_fsrs,
        passo_fsrs=cartao.passo_fsrs,
    )


def _gravar_estado(cartao: Cartao, estado: EstadoCartaoFsrs) -> None:
    """Copia `estado` para as colunas de `cartao` (mesmo objeto, novo ou já existente)."""
    cartao.stability = estado.stability
    cartao.difficulty = estado.difficulty
    cartao.due = estado.due
    cartao.reps = estado.reps
    cartao.lapses = estado.lapses
    cartao.last_review = estado.last_review
    cartao.estado_fsrs = estado.estado_fsrs
    cartao.passo_fsrs = estado.passo_fsrs


def buscar_cartao_da_questao(db: Session, usuario_id: UUID, questao_id: UUID) -> Cartao | None:
    """O cartão deste usuário para esta questão, se já existir.

    Args:
        db: sessão do request.
        usuario_id: dono do cartão.
        questao_id: questão de origem.

    Returns:
        O `Cartao`, ou `None` se a questão ainda não gerou um.
    """
    consulta = select(Cartao).where(
        Cartao.usuario_id == usuario_id, Cartao.questao_id == questao_id
    )
    return db.scalars(consulta).first()


def registrar_erro(
    db: Session, usuario: Usuario, questao: Questao, confianca: Confianca, agora: datetime
) -> Cartao | None:
    """Faz nascer (ou, defensivamente, atualiza) o cartão de uma questão errada.

    Idempotente por `(usuario, questao)` — `buscar_cartao_da_questao` antes de criar é o que
    cumpre "não regenere o que já existe": no fluxo normal a questão só é vista uma vez
    (`repositorio_questao.proxima_questao` a exclui depois de respondida), então este caminho
    "já existe" é defensivo, não o caso comum.

    Args:
        db: sessão do request.
        usuario: quem errou.
        questao: a questão errada; só cria cartão quando `questao.topico_id` não é `None` —
            `Cartao.topico_id` é `NOT NULL` e uma questão sem tópico casado nunca é publicável
            (não deveria chegar aqui, mas a função não força o dado).
        confianca: `"certeza"`/`"duvida"`, a mesma declarada antes de responder.
        agora: instante do erro (`dados/base.py::agora_utc`).

    Returns:
        O `Cartao` criado ou atualizado; `None` quando `questao.topico_id` é `None` (nada para
        gravar, sem violar a coluna `NOT NULL`).
    """
    if questao.topico_id is None:
        return None

    cartao = buscar_cartao_da_questao(db, usuario.id, questao.id)
    estado_atual = _estado_do_cartao(cartao) if cartao is not None else None
    novo_estado = revisar(estado_atual, acertou=False, confianca=confianca, agora=agora)

    if cartao is None:
        frente, verso = montar_frente_verso(
            comando=questao.comando, enunciado=questao.enunciado, gabarito=questao.gabarito
        )
        cartao = Cartao(
            usuario_id=usuario.id,
            questao_id=questao.id,
            topico_id=questao.topico_id,
            frente=frente,
            verso=verso,
            origem=ORIGEM_AUTO_ERRO,
        )
        db.add(cartao)
    _gravar_estado(cartao, novo_estado)
    db.flush()
    return cartao


def cartoes_vencidos(db: Session, usuario_id: UUID, agora: datetime) -> list[Cartao]:
    """Os cartões vencidos deste usuário, na ordem do FSRS (`due` crescente).

    Args:
        db: sessão do request.
        usuario_id: dono dos cartões.
        agora: instante de referência (`dados/base.py::agora_utc`) — vencido é `due <= agora`.

    Returns:
        Os `Cartao` vencidos, mais antigo primeiro; lista vazia sem nenhum vencido.
    """
    consulta = (
        select(Cartao)
        .where(Cartao.usuario_id == usuario_id, Cartao.due <= agora)
        .order_by(Cartao.due, Cartao.id)
    )
    return list(db.scalars(consulta).all())


def revisar_cartao(
    db: Session,
    usuario: Usuario,
    cartao: Cartao,
    *,
    acertou: bool,
    resposta: str | None,
    confianca: Confianca,
    tempo_ms: int,
    agora: datetime,
) -> EventoEstudo:
    """Aplica uma revisão: grava `EventoEstudo(tipo="revisao_cartao")` e atualiza o estado FSRS.

    As duas gravações acontecem sempre juntas — nunca só uma: o evento é o fato bruto (append-
    only, alimenta o calibrador e o painel); o cartão é o estado agregado que decide a próxima
    agenda.

    Args:
        db: sessão do request.
        usuario: quem revisou.
        cartao: o cartão revisado (de `cartoes_vencidos`).
        acertou: se a resposta desta revisão bateu com o gabarito (cartões sem `questao_id`,
            quando existirem, informam isto por fora — fora do escopo desta fatia).
        resposta: o que a pessoa respondeu, quando a revisão é de uma questão; `None` senão.
        confianca: `"certeza"`/`"duvida"`.
        tempo_ms: tempo gasto na revisão, em milissegundos.
        agora: instante da revisão (`dados/base.py::agora_utc`).

    Returns:
        O `EventoEstudo` gravado.
    """
    novo_estado = revisar(
        _estado_do_cartao(cartao), acertou=acertou, confianca=confianca, agora=agora
    )
    _gravar_estado(cartao, novo_estado)

    evento = EventoEstudo(
        usuario_id=usuario.id,
        ocorrido_em=agora,
        tipo="revisao_cartao",
        questao_id=cartao.questao_id,
        cartao_id=cartao.id,
        acertou=acertou,
        resposta=resposta,
        tempo_ms=tempo_ms,
        confianca_declarada=confianca,
    )
    db.add(evento)
    db.flush()
    return evento
