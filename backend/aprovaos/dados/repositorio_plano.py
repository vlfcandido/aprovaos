"""Repositório de `plano_dia`/`bloco` (fatia 8, F3.x): monta a entrada e persiste as ações.

O que é: `usuarios_ativos` (quem o job noturno processa), `gerar_ou_obter_plano_noturno`
(idempotente — versão 1 do dia, geração noturna sem check-in), `registrar_checkin` (a reescrita —
versão N+1 do mesmo dia, nunca um plano novo), `iniciar_bloco`/`concluir_bloco`/`pular_bloco`
(ação sobre um bloco existente), `discordar_bloco` (troca um bloco por outra alternativa, F3.3/
F3.4) e `dias_para_prova_do_dia` (de exibição, para a tela mostrar "faltam N dias" — RF-19, fatia
10 §7). `_dias_para_prova` (privada) resolve `perfil.data_alvo - dia` para `dominio.plano.
montar_plano` nas duas funções que geram plano de verdade — nem `motor/plano.py` nem
`api/plano.py` precisam saber disso, já chegam até aqui via `gerar_ou_obter_plano_noturno`/
`registrar_checkin`. Todas fazem `add`/`flush`; o `commit` é sempre da rota ou do comando
(convenção transversal dos outros repositórios). Quando ler: ao ligar `api/plano.py` ou
`motor/plano.py`.
"""

from datetime import date, datetime
from datetime import time as _time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import (
    Bloco,
    EventoEstudo,
    PerfilEstudo,
    PlanoDia,
    Topico,
    TopicoEdital,
    Usuario,
)
from aprovaos.dados.repositorio_aula import aula_publicada_do_topico
from aprovaos.dados.repositorio_cartao import cartoes_vencidos
from aprovaos.dados.repositorio_edital import concurso_principal, edital_atual
from aprovaos.dados.repositorio_fio_memoria import estatisticas_topicos_vistos
from aprovaos.dados.repositorio_perfil import perfil_atual
from aprovaos.dados.repositorio_questao import contagem_por_topico
from aprovaos.dominio.erros import SemConcursoPrincipal
from aprovaos.dominio.plano import (
    BlocoPlanejado,
    CandidatoBloco,
    ResultadoPlano,
    TopicoParaPlano,
    escolher_substituto,
    montar_candidatos,
    montar_plano,
)
from aprovaos.dominio.rotina import DIAS_SEMANA
from aprovaos.dominio.trilha import TopicoParaTrilha, montar_trilha

MENSAGEM_SEM_ROTINA = "Configure sua rotina em /rotina antes de gerar o plano do dia."
MENSAGEM_SEM_CONCURSO = "Sem concurso principal ou edital para planejar — suba um edital primeiro."

#: Hora usada só quando um bloco antigo (defensivo) não tem `hora_sugerida` gravada — nunca
#: acontece no caminho normal (`_gravar_plano` sempre preenche), mas evita `None` propagar para
#: `BlocoPlanejado.hora_sugerida`, que não é opcional no domínio.
_HORA_PADRAO = _time(8, 0)

_EVENTO_POR_ACAO = {
    "iniciar": "bloco_iniciado",
    "concluir": "bloco_concluido",
    "pular": "bloco_pulado",
}


def usuarios_ativos(db: Session) -> list[Usuario]:
    """Usuários que o job noturno deve processar hoje.

    Definição provisória (plano `docs/fatias/8-plano-do-dia.md` §8, P-47): sem `excluido_em` e
    com pelo menos uma `perfil_estudo` gravada — sem rotina não há `tempo_min` para planejar
    nada. Quando existir um sinal melhor (assinatura ativa, último acesso), só esta função muda.

    Args:
        db: sessão do comando/request.

    Returns:
        Os `Usuario` elegíveis, sem ordem garantida.
    """
    consulta = (
        select(Usuario)
        .join(PerfilEstudo, PerfilEstudo.usuario_id == Usuario.id)
        .where(Usuario.excluido_em.is_(None))
        .distinct()
    )
    return list(db.scalars(consulta).all())


def _topicos_para_plano(db: Session, edital_id: UUID, usuario_id: UUID) -> list[TopicoParaPlano]:
    """Os tópicos do edital, na ordem da trilha, com a flag de aula publicada resolvida.

    Reaproveita `contagem_por_topico` (peso medido) e `estatisticas_topicos_vistos` (histórico) —
    a mesma entrada de `dominio.trilha.montar_trilha` usada pela fatia 6 — em vez de duplicar a
    consulta de `motor.dossie.topicos_de_maior_peso`: `dados/` não importa `motor/` (a direção da
    dependência é a oposta), então a trilha é remontada aqui a partir de repositórios-irmãos.

    Args:
        db: sessão do request/comando.
        edital_id: edital do concurso principal.
        usuario_id: aluno (para o histórico de `estatisticas_topicos_vistos`).

    Returns:
        Um `TopicoParaPlano` por tópico do edital, na ordem de `montar_trilha` (não-visto/fraco
        antes de dominado, mais peso primeiro).
    """
    contagem = contagem_por_topico(db, edital_id)
    consulta = (
        select(Topico.id, Topico.slug, Topico.materia, Topico.nome)
        .join(TopicoEdital, TopicoEdital.topico_id == Topico.id)
        .where(TopicoEdital.edital_id == edital_id)
    )
    topicos_trilha = [
        TopicoParaTrilha(
            topico_id=topico_id,
            slug=slug,
            nome=nome,
            materia=materia,
            questoes_publicaveis=contagem.get(topico_id, 0),
        )
        for topico_id, slug, materia, nome in db.execute(consulta).all()
    ]
    vistos = {e.topico_id: e for e in estatisticas_topicos_vistos(db, usuario_id, edital_id)}
    itens = montar_trilha(topicos_trilha, vistos)
    return [
        TopicoParaPlano(
            topico_id=item.topico_id,
            slug=item.slug,
            nome=item.nome,
            materia=item.materia,
            questoes_publicaveis=item.questoes_publicaveis,
            tem_aula=aula_publicada_do_topico(db, item.topico_id) is not None,
            status=item.status,
            motivo_trilha=item.motivo,
        )
        for item in itens
    ]


def _preparar_entrada(db: Session, usuario: Usuario) -> tuple[PerfilEstudo, list[TopicoParaPlano]]:
    """Resolve `perfil_estudo` e os tópicos do edital do concurso principal, ou levanta o motivo.

    Args:
        db: sessão do request/comando.
        usuario: dono do plano.

    Returns:
        `(perfil, topicos)`.

    Raises:
        SemConcursoPrincipal: sem rotina configurada, ou sem concurso principal/edital.
    """
    perfil = perfil_atual(db, usuario.id)
    if perfil is None:
        raise SemConcursoPrincipal(MENSAGEM_SEM_ROTINA)
    concurso = concurso_principal(db, usuario.tenant_id)
    edital = edital_atual(db, concurso.id) if concurso is not None else None
    if edital is None:
        raise SemConcursoPrincipal(MENSAGEM_SEM_CONCURSO)
    topicos = _topicos_para_plano(db, edital.id, usuario.id)
    return perfil, topicos


def _tempo_min_do_dia(perfil: PerfilEstudo, dia: date) -> int:
    """Minutos disponíveis no dia da semana de `dia`, a partir de `perfil.horas_por_dia_semana`."""
    chave = DIAS_SEMANA[dia.weekday()]
    horas = float(perfil.horas_por_dia_semana.get(chave, 0.0))
    return round(horas * 60)


def _dias_para_prova(perfil: PerfilEstudo, dia: date) -> int | None:
    """`(perfil.data_alvo - dia).days`, ou `None` sem `data_alvo` (RF-19, fatia 10 §7).

    A origem real de `dominio.plano.montar_plano(dias_para_prova=...)` — sem `data_alvo`, o
    regime de semana da prova nunca liga (`dominio.plano._em_semana_prova` trata `None` como
    "fora da janela").
    """
    if perfil.data_alvo is None:
        return None
    return (perfil.data_alvo - dia).days


def dias_para_prova_do_dia(db: Session, usuario_id: UUID, dia: date) -> int | None:
    """`dias_para_prova` de exibição (`web/templates/hoje/pagina.html`), fora do plano.

    Usa o `perfil_estudo` mais recente, mesmo raciocínio de `_dias_para_prova`, mas sem exigir
    um `PlanoDia` já gravado — a tela chama isto direto para mostrar "faltam N dias".

    Args:
        db: sessão do request.
        usuario_id: dono do perfil.
        dia: o dia mostrado na tela (`plano.data`).

    Returns:
        `(perfil.data_alvo - dia).days`, ou `None` sem perfil ou sem `data_alvo`.
    """
    perfil = perfil_atual(db, usuario_id)
    if perfil is None:
        return None
    return _dias_para_prova(perfil, dia)


def _buscar_versao(db: Session, usuario_id: UUID, dia: date, versao: int) -> PlanoDia | None:
    """A linha exata `(usuario_id, dia, versao)`, ou `None`."""
    consulta = select(PlanoDia).where(
        PlanoDia.usuario_id == usuario_id, PlanoDia.data == dia, PlanoDia.versao == versao
    )
    return db.scalars(consulta).first()


def plano_mais_recente(db: Session, usuario_id: UUID, dia: date) -> PlanoDia | None:
    """A versão mais recente do plano de `dia` para este usuário, ou `None` se não existe nenhuma.

    Args:
        db: sessão do request.
        usuario_id: dono do plano.
        dia: o dia planejado.

    Returns:
        O `PlanoDia` de maior `versao`, ou `None`.
    """
    consulta = (
        select(PlanoDia)
        .where(PlanoDia.usuario_id == usuario_id, PlanoDia.data == dia)
        .order_by(PlanoDia.versao.desc())
    )
    return db.scalars(consulta).first()


def _gravar_plano(
    db: Session,
    usuario_id: UUID,
    dia: date,
    versao: int,
    energia: int | None,
    sono_h: float | None,
    resultado: ResultadoPlano,
    agora: datetime,
) -> PlanoDia:
    """Grava `resultado` como uma nova linha de `plano_dia` (+ `bloco`s filhos)."""
    plano = PlanoDia(
        usuario_id=usuario_id,
        data=dia,
        versao=versao,
        gerado_em=agora,
        energia=energia,
        sono_h=sono_h,
        tempo_min=resultado.tempo_min,
        modo=resultado.modo,
        porque_geral=resultado.porque_geral,
    )
    for bloco in resultado.blocos:
        plano.blocos.append(
            Bloco(
                ordem=bloco.ordem,
                tipo=bloco.tipo,
                topico_id=bloco.topico_id,
                duracao_min=bloco.duracao_min,
                hora_sugerida=bloco.hora_sugerida,
                porque=bloco.porque,
            )
        )
    db.add(plano)
    db.flush()
    return plano


def gerar_ou_obter_plano_noturno(
    db: Session, usuario: Usuario, dia: date, agora: datetime | None = None
) -> PlanoDia:
    """Devolve a versão 1 do plano de `dia`; gera na primeira chamada, idempotente depois.

    É a função que tanto o job noturno (`motor/plano.py`) quanto `GET /hoje` (quando o cron ainda
    não rodou) chamam — a segunda chamada do mesmo dia nunca duplica a versão 1.

    Args:
        db: sessão do request/comando.
        usuario: dono do plano.
        dia: o dia a planejar.
        agora: instante da geração; `None` usa `agora_utc()`.

    Returns:
        O `PlanoDia` (versão 1) já existente ou recém-gravado.

    Raises:
        SemConcursoPrincipal: sem rotina configurada, ou sem concurso principal/edital — o
            chamador decide o que mostrar/registrar.
    """
    instante = agora if agora is not None else agora_utc()
    existente = _buscar_versao(db, usuario.id, dia, 1)
    if existente is not None:
        return existente

    perfil, topicos = _preparar_entrada(db, usuario)
    tempo_min = _tempo_min_do_dia(perfil, dia)
    qtd_vencidos = len(cartoes_vencidos(db, usuario.id, instante))
    resultado = montar_plano(
        topicos,
        qtd_vencidos,
        tempo_min,
        energia=None,
        sono_h=None,
        pediu_descanso=False,
        horario_preferido=perfil.horario_preferido,
        dias_para_prova=_dias_para_prova(perfil, dia),
    )
    return _gravar_plano(db, usuario.id, dia, 1, None, None, resultado, instante)


def registrar_checkin(
    db: Session,
    usuario: Usuario,
    dia: date,
    energia: int,
    sono_h: float,
    tempo_min: int,
    pediu_descanso: bool,
    agora: datetime | None = None,
) -> PlanoDia:
    """Reescreve o plano de `dia`: grava a próxima versão (nunca um plano novo) + o evento.

    Garante primeiro que a versão 1 existe (mesmo raciocínio da fatia 7 para o diagnóstico: um
    check-in sem plano noturno prévio ainda assim funciona).

    Args:
        db: sessão do request.
        usuario: quem fez o check-in.
        dia: o dia do check-in (hoje, na prática).
        energia: `1`–`5` declarada.
        sono_h: horas de sono declaradas.
        tempo_min: minutos reais disponíveis, declarados no check-in (substitui o padrão do
            perfil só para esta versão).
        pediu_descanso: `True` quando a aluna apertou "Hoje quero descansar".
        agora: instante do check-in; `None` usa `agora_utc()`.

    Returns:
        O novo `PlanoDia` (versão = máxima existente + 1).

    Raises:
        SemConcursoPrincipal: sem rotina configurada, ou sem concurso principal/edital.
    """
    instante = agora if agora is not None else agora_utc()
    gerar_ou_obter_plano_noturno(db, usuario, dia, instante)  # garante a versão 1
    _, topicos = _preparar_entrada(db, usuario)
    qtd_vencidos = len(cartoes_vencidos(db, usuario.id, instante))
    perfil = perfil_atual(db, usuario.id)
    assert perfil is not None  # garantido por _preparar_entrada, chamada acima

    resultado = montar_plano(
        topicos,
        qtd_vencidos,
        tempo_min,
        energia=energia,
        sono_h=sono_h,
        pediu_descanso=pediu_descanso,
        horario_preferido=perfil.horario_preferido,
        dias_para_prova=_dias_para_prova(perfil, dia),
    )
    ultima = plano_mais_recente(db, usuario.id, dia)
    proxima_versao = (ultima.versao if ultima is not None else 0) + 1
    plano = _gravar_plano(db, usuario.id, dia, proxima_versao, energia, sono_h, resultado, instante)

    db.add(
        EventoEstudo(
            usuario_id=usuario.id,
            ocorrido_em=instante,
            tipo="checkin",
            energia=energia,
            dados={"sono_h": sono_h, "tempo_min": tempo_min, "pediu_descanso": pediu_descanso},
        )
    )
    db.flush()
    return plano


def buscar_bloco_do_usuario(db: Session, usuario_id: UUID, bloco_id: UUID) -> Bloco | None:
    """O `Bloco` só é aceito se pertence a um `PlanoDia` deste usuário.

    Mesmo isolamento por dono de `api.questoes._questao_pendente`: sem essa checagem, um
    `bloco_id` de outra conta seria manipulável só sabendo o `id`.

    Args:
        db: sessão do request.
        usuario_id: dono esperado.
        bloco_id: chave do bloco, vinda da URL.

    Returns:
        O `Bloco`, ou `None` se não existir ou não pertencer a este usuário.
    """
    consulta = (
        select(Bloco)
        .join(PlanoDia, Bloco.plano_dia_id == PlanoDia.id)
        .where(Bloco.id == bloco_id, PlanoDia.usuario_id == usuario_id)
    )
    return db.scalars(consulta).first()


def _agir_no_bloco(
    db: Session, usuario: Usuario, bloco: Bloco, acao: str, agora: datetime
) -> EventoEstudo:
    """Atualiza `status`/`iniciado_em`/`concluido_em` de `bloco` e grava o evento de `acao`."""
    if acao == "iniciar":
        bloco.status = "iniciado"
        bloco.iniciado_em = agora
    elif acao == "concluir":
        bloco.status = "concluido"
        bloco.concluido_em = agora
    elif acao == "pular":
        bloco.status = "pulado"
        bloco.concluido_em = agora
    evento = EventoEstudo(
        usuario_id=usuario.id,
        ocorrido_em=agora,
        tipo=_EVENTO_POR_ACAO[acao],
        bloco_id=bloco.id,
    )
    db.add(evento)
    db.flush()
    return evento


def iniciar_bloco(db: Session, usuario: Usuario, bloco: Bloco, agora: datetime) -> EventoEstudo:
    """Marca `bloco` como iniciado e grava `EventoEstudo(tipo="bloco_iniciado")`."""
    return _agir_no_bloco(db, usuario, bloco, "iniciar", agora)


def concluir_bloco(db: Session, usuario: Usuario, bloco: Bloco, agora: datetime) -> EventoEstudo:
    """Marca `bloco` como concluído e grava `EventoEstudo(tipo="bloco_concluido")`."""
    return _agir_no_bloco(db, usuario, bloco, "concluir", agora)


def pular_bloco(db: Session, usuario: Usuario, bloco: Bloco, agora: datetime) -> EventoEstudo:
    """Marca `bloco` como pulado e grava `EventoEstudo(tipo="bloco_pulado")`."""
    return _agir_no_bloco(db, usuario, bloco, "pular", agora)


def discordar_bloco(
    db: Session, usuario: Usuario, bloco: Bloco, motivo: str, agora: datetime
) -> tuple[Bloco | None, EventoEstudo]:
    """Troca `bloco` por outra alternativa que ainda não está no plano de hoje (F3.3/F3.4).

    Sempre grava o evento `discordou` — mesmo sem substituto disponível, o "discordo" em si já é
    sinal (para o calibrador futuro). Quando há substituto, o bloco antigo vira
    `status="trocado"` (nunca some — o porquê original continua auditável) e um `Bloco` novo
    nasce na mesma `ordem`, com o motivo da aluna na frente do `porque` do substituto.

    Args:
        db: sessão do request.
        usuario: quem discordou.
        bloco: o bloco que ela quer trocar (já confirmado como dela).
        motivo: uma das chaves de `dominio.plano.MOTIVOS_DISCORDAR`.
        agora: instante da troca.

    Returns:
        `(bloco_novo, evento)`; `bloco_novo` é `None` quando não há alternativa (o bloco antigo
        continua como estava, a rota avisa).
    """
    plano = db.get(PlanoDia, bloco.plano_dia_id)
    assert plano is not None  # veio de _bloco_do_usuario, que já fez o join com plano_dia
    _, topicos = _preparar_entrada(db, usuario)
    qtd_vencidos = len(cartoes_vencidos(db, usuario.id, agora))
    candidatos: list[CandidatoBloco] = montar_candidatos(topicos, qtd_vencidos, restrito=False)

    blocos_planejados = [
        BlocoPlanejado(
            ordem=b.ordem,
            tipo=b.tipo,
            topico_id=b.topico_id,
            duracao_min=b.duracao_min,
            hora_sugerida=b.hora_sugerida or _HORA_PADRAO,
            porque=b.porque,
        )
        for b in plano.blocos
        if b.status != "trocado"
    ]
    bloco_atual_planejado = next(bp for bp in blocos_planejados if bp.ordem == bloco.ordem)
    tempo_restante = plano.tempo_min - sum(
        bp.duracao_min for bp in blocos_planejados if bp.ordem != bloco.ordem
    )
    substituto = escolher_substituto(
        candidatos, bloco_atual_planejado, blocos_planejados, tempo_restante
    )

    evento = EventoEstudo(
        usuario_id=usuario.id,
        ocorrido_em=agora,
        tipo="discordou",
        bloco_id=bloco.id,
        dados={
            "motivo": motivo,
            "substituto_tipo": substituto.tipo if substituto is not None else None,
        },
    )
    db.add(evento)

    bloco_novo: Bloco | None = None
    if substituto is not None:
        bloco.status = "trocado"
        bloco_novo = Bloco(
            plano_dia_id=plano.id,
            ordem=bloco.ordem,
            tipo=substituto.tipo,
            topico_id=substituto.topico_id,
            duracao_min=substituto.duracao_min,
            hora_sugerida=bloco.hora_sugerida,
            porque=f"Você disse: {motivo}. {substituto.porque}",
        )
        db.add(bloco_novo)
    db.flush()
    return bloco_novo, evento
