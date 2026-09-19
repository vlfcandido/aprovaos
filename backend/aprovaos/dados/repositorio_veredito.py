"""Repositório de `veredito_questao`: grava cada tentativa de validação de uma inédita (fatia 5).

O que é: `registrar_veredito`, que grava um `dominio.validacao_questao.Veredito` como a próxima
linha do histórico append-only de uma `Questao` — aprovado ou reprovado, a linha fica sempre
(RF-28: "rejeição registrada com motivo", nunca descartada em silêncio); e `veredictos_da_questao`,
a leitura desse histórico em ordem cronológica. Como o resto dos repositórios: funções soltas
recebendo `Session` como primeiro parâmetro, fazem `add`/`flush`; o `commit` é sempre de quem
chama (`aprovaos.motor.gerar_questao`).

Quando ler: ao ligar o comando `motor/gerar_questao.py`, ou ao investigar o histórico de
validação de uma inédita específica.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import VereditoQuestao
from aprovaos.dominio.validacao_questao import Veredito


def registrar_veredito(db: Session, questao_id: UUID, veredito: Veredito) -> VereditoQuestao:
    """Grava `veredito` como a próxima linha do histórico de validação de `questao_id`.

    Args:
        db: sessão do comando (faz `add`/`flush`; o `commit` é de quem chama).
        questao_id: a questão avaliada.
        veredito: o `Veredito` desta tentativa — aprovado ou não, sempre gravado.

    Returns:
        O `VereditoQuestao` recém-criado.
    """
    linha = VereditoQuestao(
        questao_id=questao_id,
        aprovado=veredito.aprovado,
        motivos=list(veredito.motivos),
        validador_versao=veredito.validador_versao,
        criado_em=agora_utc(),
    )
    db.add(linha)
    db.flush()
    return linha


def veredictos_da_questao(db: Session, questao_id: UUID) -> list[VereditoQuestao]:
    """O histórico de tentativas de validação de `questao_id`, da mais antiga para a mais nova.

    Args:
        db: sessão do request/comando (só leitura).
        questao_id: a questão cujo histórico se quer.

    Returns:
        As `VereditoQuestao` de `questao_id`, ordenadas por `criado_em`; vazia se nunca foi
        avaliada.
    """
    consulta = (
        select(VereditoQuestao)
        .where(VereditoQuestao.questao_id == questao_id)
        .order_by(VereditoQuestao.criado_em)
    )
    return list(db.scalars(consulta).all())
