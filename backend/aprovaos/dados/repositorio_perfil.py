"""Repositório de `perfil_estudo` (fatia 7, F2.2; fatia 1b, F1.3): rotina e "meus concursos".

O que é: `salvar_perfil` (grava uma nova versão e o consentimento de dados de rotina no
`usuario`, na mesma chamada — R-01), `perfil_atual` (a versão mais recente de um usuário),
`marcar_principal` e `alternar_acompanhamento` (fatia 1b: trocam só `concurso_principal_id`/
`concursos_acompanhados`, preservando o resto da rotina da versão anterior). Quando ler: ao
ligar o formulário `POST /rotina`, as rotas `/perfil/principal`/`/radar/{evento_url}/acompanhar`,
ou ao decidir o concurso principal de um usuário (`repositorio_edital.concurso_principal` lê
`perfil_atual`). Funções soltas recebendo `Session` como primeiro parâmetro, fazem `add`/
`flush`; o `commit` é sempre da rota.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import PerfilEstudo, Usuario
from aprovaos.dominio.erros import SemConcursoPrincipal
from aprovaos.dominio.rotina import VERSAO_CONSENTIMENTO_ROTINA, DadosRotina

MENSAGEM_SEM_ROTINA = "Configure sua rotina antes de escolher ou acompanhar concursos."


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


def _proxima_versao_a_partir_de(
    atual: PerfilEstudo, usuario: Usuario, **sobrescritas: object
) -> PerfilEstudo:
    """Cria a versão seguinte de `perfil_estudo`, copiando a rotina de `atual`.

    Só troca o que vier em `sobrescritas` — nunca reseta `horas_por_dia_semana`/
    `concursos_acompanhados` por omissão (`PerfilEstudo` tem `default=list`/campos obrigatórios;
    sem copiar, a próxima versão nasceria sem o que a versão anterior já sabia).
    """
    campos: dict[str, object] = {
        "usuario": usuario,
        "versao": atual.versao + 1,
        "horas_por_dia_semana": dict(atual.horas_por_dia_semana),
        "horario_preferido": atual.horario_preferido,
        "energia_tipica": atual.energia_tipica,
        "data_alvo": atual.data_alvo,
        "concurso_principal_id": atual.concurso_principal_id,
        "concursos_acompanhados": list(atual.concursos_acompanhados),
    }
    campos.update(sobrescritas)
    return PerfilEstudo(**campos)


def marcar_principal(db: Session, usuario: Usuario, concurso_id: UUID) -> PerfilEstudo:
    """Grava uma nova versão do perfil com outro `concurso_principal_id` (F1.3, "só um principal").

    Args:
        db: sessão do request.
        usuario: dono do perfil.
        concurso_id: o `Concurso` que passa a ser o principal (a rota confere que é do tenant).

    Returns:
        O `PerfilEstudo` novo.

    Raises:
        SemConcursoPrincipal: o usuário ainda não tem rotina (`perfil_estudo`) — a rota deve
            mandar para `/rotina` primeiro (mesmo critério de `motor/plano.py`).
    """
    atual = perfil_atual(db, usuario.id)
    if atual is None:
        raise SemConcursoPrincipal(MENSAGEM_SEM_ROTINA)
    novo = _proxima_versao_a_partir_de(atual, usuario, concurso_principal_id=concurso_id)
    db.add(novo)
    db.flush()
    return novo


def alternar_acompanhamento(db: Session, usuario: Usuario, evento_url: str) -> PerfilEstudo:
    """Adiciona ou remove um `evento_url` do radar em `concursos_acompanhados` (toggle, F1.3).

    Args:
        db: sessão do request.
        usuario: dono do perfil.
        evento_url: identidade do concurso do radar (`ConcursoRadar.evento_url`).

    Returns:
        O `PerfilEstudo` novo, com o `evento_url` presente ou ausente conforme o toggle.

    Raises:
        SemConcursoPrincipal: o usuário ainda não tem rotina (`perfil_estudo`).
    """
    atual = perfil_atual(db, usuario.id)
    if atual is None:
        raise SemConcursoPrincipal(MENSAGEM_SEM_ROTINA)
    acompanhados = list(atual.concursos_acompanhados)
    if evento_url in acompanhados:
        acompanhados.remove(evento_url)
    else:
        acompanhados.append(evento_url)
    novo = _proxima_versao_a_partir_de(atual, usuario, concursos_acompanhados=acompanhados)
    db.add(novo)
    db.flush()
    return novo
