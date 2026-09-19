"""Exportar e excluir os dados de um usuário (RF-23, Ruling 48, modelo de dados §5).

O que é: `exportar_dados_do_usuario` (tudo que é do usuário, em um dicionário serializável em
JSON) e `excluir_dados_do_usuario` (anonimiza a conta, apaga `cartao`/`perfil_estudo` — modelo de
dados §5 — e revoga toda sessão aberta). "No dia em que existe pagamento existe relação de
consumo, e o produto já guarda energia/sono" (Ruling 48): esta fatia entrega os dois junto com o
billing, não depois. Quando ler: ao mexer em `GET /conta/exportar` ou `POST /conta/excluir`, ou ao
acrescentar uma tabela nova que pendura dado pessoal em `usuario_id`.

**Lacuna declarada** (`docs/PENDENCIAS.md`): o modelo de dados §5 promete "eventos ficam sem
usuario_id" na exclusão; `evento_estudo.usuario_id` é hoje `NOT NULL` (a coluna nunca foi pensada
como nullable) — torná-la nullable é mudança de esquema que esta fatia não faz. A conta fica
inacessível e anonimizada (e-mail/senha/`google_sub` apagados, sessões revogadas) e
`cartao`/`perfil_estudo` são apagados de verdade, como o modelo de dados pede; `evento_estudo`
continua ligado ao `usuario_id` antigo, sem identificar mais ninguém de fora do banco.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import (
    Assinatura,
    Cartao,
    EventoEstudo,
    PerfilEstudo,
    ReporteErro,
    Usuario,
)
from aprovaos.dados.repositorio_sessao import revogar_todas_as_sessoes


def _serializavel(valor: Any) -> Any:
    """Converte um valor de coluna para algo que `json.dumps` aceita direto."""
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, UUID):
        return str(valor)
    if isinstance(valor, Decimal):
        return str(valor)
    return valor


def _linha_para_dict(colunas: dict[str, Any]) -> dict[str, Any]:
    """Aplica `_serializavel` a cada valor de um dicionário de coluna→valor."""
    return {chave: _serializavel(valor) for chave, valor in colunas.items()}


def exportar_dados_do_usuario(db: Session, usuario: Usuario) -> dict[str, Any]:
    """Monta o export completo (RF-23): conta, assinatura, eventos, cartões e perfis.

    Args:
        db: sessão do request (só leitura).
        usuario: o usuário exportando os próprios dados.

    Returns:
        Um dicionário serializável em JSON (`json.dumps` direto, sem `default=`) com as chaves
        `conta`, `assinatura`, `eventos_estudo`, `cartoes`, `perfil_estudo` e `reportes_erro`.
    """
    assinatura = db.scalars(select(Assinatura).where(Assinatura.usuario_id == usuario.id)).first()
    eventos = db.scalars(select(EventoEstudo).where(EventoEstudo.usuario_id == usuario.id)).all()
    cartoes = db.scalars(select(Cartao).where(Cartao.usuario_id == usuario.id)).all()
    perfis = db.scalars(select(PerfilEstudo).where(PerfilEstudo.usuario_id == usuario.id)).all()
    reportes = db.scalars(select(ReporteErro).where(ReporteErro.usuario_id == usuario.id)).all()

    return {
        "conta": {
            "email": usuario.email,
            "criado_em": _serializavel(usuario.criado_em),
            "consentimento_dados_rotina": usuario.consentimento_dados_rotina,
        },
        "assinatura": (
            _linha_para_dict(
                {
                    "tier": assinatura.tier,
                    "periodicidade": assinatura.periodicidade,
                    "status": assinatura.status,
                    "inicio": assinatura.inicio,
                    "fim": assinatura.fim,
                    "cancelada_em": assinatura.cancelada_em,
                }
            )
            if assinatura is not None
            else None
        ),
        "eventos_estudo": [
            _linha_para_dict(
                {
                    "ocorrido_em": e.ocorrido_em,
                    "tipo": e.tipo,
                    "questao_id": e.questao_id,
                    "acertou": e.acertou,
                    "resposta": e.resposta,
                    "confianca_declarada": e.confianca_declarada,
                }
            )
            for e in eventos
        ],
        "cartoes": [
            _linha_para_dict(
                {
                    "topico_id": c.topico_id,
                    "frente": c.frente,
                    "verso": c.verso,
                    "due": c.due,
                    "reps": c.reps,
                    "lapses": c.lapses,
                }
            )
            for c in cartoes
        ],
        "perfil_estudo": [
            _linha_para_dict(
                {
                    "versao": p.versao,
                    "horas_por_dia_semana": p.horas_por_dia_semana,
                    "horario_preferido": p.horario_preferido,
                    "energia_tipica": p.energia_tipica,
                    "data_alvo": p.data_alvo,
                }
            )
            for p in perfis
        ],
        "reportes_erro": [
            _linha_para_dict(
                {"conteudo_tipo": r.conteudo_tipo, "motivo": r.motivo, "status": r.status}
            )
            for r in reportes
        ],
    }


def excluir_dados_do_usuario(db: Session, usuario: Usuario, agora: datetime) -> None:
    """Anonimiza a conta e apaga `cartao`/`perfil_estudo` (modelo de dados §5, RF-23).

    A rota chama isto **depois** de já ter cancelado a assinatura no gateway (Ruling 48) — esta
    função só mexe no que é local. Ver o docstring do módulo para a lacuna declarada sobre
    `evento_estudo.usuario_id`.

    Args:
        db: sessão do request.
        usuario: a conta a excluir.
        agora: instante da exclusão (`dados/base.py::agora_utc`) — vira `usuario.excluido_em`.
    """
    usuario.excluido_em = agora
    usuario.email = f"excluido-{uuid4()}@anon.aprovaos"
    usuario.senha_hash = None
    usuario.google_sub = None

    db.execute(delete(Cartao).where(Cartao.usuario_id == usuario.id))
    db.execute(delete(PerfilEstudo).where(PerfilEstudo.usuario_id == usuario.id))
    revogar_todas_as_sessoes(db, usuario.id, agora)
    db.flush()
