"""Repositório de `perfil_estudo` (fatia 7, F2.2): salvar a rotina e ler a versão atual.

O que é: `salvar_perfil` (grava uma nova versão e o consentimento de dados de rotina no
`usuario`, na mesma chamada — R-01) e `perfil_atual` (a versão mais recente de um usuário).
Quando ler: ao ligar o formulário `POST /rotina`, ou ao decidir o concurso principal de um
usuário (`repositorio_edital.concurso_principal` lê `perfil_atual`). Funções soltas recebendo
`Session` como primeiro parâmetro, fazem `add`/`flush`; o `commit` é sempre da rota.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import PerfilEstudo, Usuario
from aprovaos.dominio.rotina import VERSAO_CONSENTIMENTO_ROTINA, DadosRotina


def perfil_atual(db: Session, usuario_id: UUID) -> PerfilEstudo | None:
    """A versão mais recente de `perfil_estudo` de um usuário.

    Args:
        db: sessão do request.
        usuario_id: dono do perfil.

    Returns:
        O `PerfilEstudo` de maior `versao`, ou `None` se ele nunca salvou uma rotina.
    """
    consulta = (
        select(PerfilEstudo)
        .where(PerfilEstudo.usuario_id == usuario_id)
        .order_by(PerfilEstudo.versao.desc())
    )
    return db.scalars(consulta).first()


def salvar_perfil(
    db: Session, usuario: Usuario, dados: DadosRotina, agora: datetime | None = None
) -> PerfilEstudo:
    """Grava uma nova versão da rotina e o consentimento de dados de rotina no `usuario`.

    A versão nova é sempre a maior existente + 1 (1 na primeira vez) — nunca sobrescreve a
    anterior (`perfil_estudo` é append-only, modelo de dados §2). O consentimento
    (`usuario.consentimento_dados_rotina*`) é gravado **sempre** que a rotina é salva: a rota só
    chama esta função depois de confirmar que o checkbox de consentimento veio marcado
    (R-01) — salvar a rotina sem consentir energia/sono não é um caminho que esta função aceita
    decidir sozinha.

    Args:
        db: sessão do request.
        usuario: dono do perfil (também recebe o consentimento).
        dados: a rotina já validada (`dominio.rotina.DadosRotina`).
        agora: instante do aceite; `None` usa `agora_utc()` (testes podem fixar um valor).

    Returns:
        O `PerfilEstudo` novo, já com `id` e `versao` preenchidos.
    """
    instante = agora if agora is not None else agora_utc()
    ultima_versao = db.scalar(
        select(func.max(PerfilEstudo.versao)).where(PerfilEstudo.usuario_id == usuario.id)
    )
    perfil = PerfilEstudo(
        usuario=usuario,
        versao=(ultima_versao or 0) + 1,
        horas_por_dia_semana=dict(dados.horas_por_dia_semana),
        horario_preferido=dados.horario_preferido,
        energia_tipica=dados.energia_tipica,
        data_alvo=dados.data_alvo,
        concurso_principal_id=dados.concurso_principal_id,
    )
    usuario.consentimento_dados_rotina = True
    usuario.consentimento_dados_rotina_em = instante
    usuario.consentimento_dados_rotina_versao = VERSAO_CONSENTIMENTO_ROTINA
    db.add(perfil)
    db.flush()
    return perfil
