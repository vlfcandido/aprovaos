"""Repositório de questões: grava o que o curador produziu e serve as consultas de estudo.

O que é: `salvar_questoes` (dedup por `hash_dedup`, sem depender de `IntegrityError` para
funcionar; grava também as `Alternativa` de uma `QuestaoCurada` de múltipla escolha — passo 2 da
V3b), `atualizar_classificacao` (passo 12b — reclassifica uma questão já gravada sem duplicar
nem tocar texto/gabarito/origem/alternativas), `contagem_por_topico` (quantas publicáveis por
tópico de um edital, para o "0 de 36" da V2 virar contagem real), `proxima_questao` (a próxima
publicável de um tópico que o usuário nunca respondeu nem reportou — premissa H do plano da V3),
`registrar_resposta`/`registrar_reporte` (gravam `evento_estudo`, nunca alteram `questao`;
`registrar_resposta` aceita `dados` opcional — V5, o JSON livre que o fio da memória usa) e
`topicos_vistos` (premissa N: tópicos com pelo menos uma resposta do usuário naquele edital).
Quando ler: ao ligar o comando de curadoria (passo 12) ou as rotas de questão (passo 13). Como o
repositório da V2 (`repositorio_edital.py`): funções soltas recebendo `Session` como primeiro
parâmetro, fazem `add`/`flush`; o `commit` é sempre da rota/comando.

**Fatia 11 (fecha a P-34):** toda consulta que serve conteúdo aqui (`contagem_por_topico`,
`proxima_questao`, `questoes_publicaveis_do_topico`) passa a filtrar também
`Questao.despublicada_em.is_(None)` — é o carimbo que `dados.repositorio_calibracao.
gravar_calibracao` grava quando o calibrador decide despublicar; sem este filtro, a decisão do
calibrador nunca refletiria na fila da aluna.

**Fatia 5 (questões inéditas validadas):** `salvar_questao_inedita` grava o item que o
`gerador-de-questao` escreveu, **sempre** — aprovado ou reprovado (RF-28: "rejeição registrada
com motivo", nunca descartada em silêncio). Ao contrário de `salvar_questoes` (que já nasce
`publicavel` pelo gate da V3), aqui `publicavel`/`motivo_nao_publicavel` vêm de fora
(`dominio.validacao_questao.julgar`, rodado por `motor.gerar_questao`) porque a validação de uma
inédita depende de uma segunda chamada de IA que este módulo não faz.
"""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import (
    Alternativa,
    EventoEstudo,
    Questao,
    ReporteErro,
    Topico,
    TopicoEdital,
    Usuario,
)
from aprovaos.dominio.questao import QuestaoCurada, RegraProva, hash_dedup
from aprovaos.dominio.questao_inedita import QuestaoGerada


def salvar_questoes(db: Session, questoes: list[QuestaoCurada]) -> tuple[int, int]:
    """Grava as questões curadas que ainda não existem, deduplicando por `hash_dedup`.

    Consulta os hashes já gravados antes de inserir — a função não depende de capturar
    `IntegrityError` para funcionar; a `UNIQUE` de `questao.hash_dedup` é só a rede de segurança
    contra corrida. Rodar a mesma lista duas vezes não cria linha nova: a segunda chamada
    devolve `(0, N)`. Quando `questao.alternativas` não é `None` (múltipla escolha), grava
    também as cinco linhas de `alternativa` (letra, texto, `correta`, `justificativa=None` — quem
    a preenche é o gerador de inéditas com validador, fatia 5, nunca o curador); uma questão que
    já existe não grava alternativa nenhuma de novo — elas acompanham a questão, nunca duplicam
    sozinhas. Faz `add`/`flush`; quem commita é a rota/comando.

    Args:
        db: sessão do request/comando.
        questoes: a saída do curador (`motor.curadoria.curador.curar`).

    Returns:
        `(quantidade de linhas novas, quantidade de já existentes)`.
    """
    if not questoes:
        return 0, 0

    hashes = [questao.hash_dedup for questao in questoes]
    existentes = set(
        db.scalars(select(Questao.hash_dedup).where(Questao.hash_dedup.in_(hashes))).all()
    )
    slugs = {questao.topico_slug for questao in questoes if questao.topico_slug is not None}
    topicos_por_slug: dict[str, Topico] = {}
    if slugs:
        for encontrado in db.scalars(select(Topico).where(Topico.slug.in_(slugs))).all():
            topicos_por_slug[encontrado.slug] = encontrado

    novas = 0
    repetidas = 0
    for questao in questoes:
        if questao.hash_dedup in existentes:
            repetidas += 1
            continue
        topico: Topico | None = (
            topicos_por_slug.get(questao.topico_slug) if questao.topico_slug else None
        )
        nova_questao = Questao(
            adapter=questao.adapter,
            banca=questao.banca,
            tipo_item=questao.tipo_item,
            comando=questao.comando,
            texto_apoio=questao.texto_apoio,
            texto_apoio_itens=questao.texto_apoio_itens,
            enunciado=questao.enunciado,
            gabarito_preliminar=questao.gabarito_preliminar,
            gabarito=questao.gabarito,
            gabarito_status=questao.gabarito_status,
            publicavel=questao.publicavel,
            motivo_nao_publicavel=questao.motivo_nao_publicavel,
            regra_prova=questao.regra_prova.model_dump(mode="json"),
            topico=topico,
            topico_confianca=questao.topico_confianca,
            topico_evidencia=questao.topico_evidencia,
            origem=questao.origem.model_dump(mode="json"),
            documento_id=UUID(questao.origem.documento_id),
            hash_dedup=questao.hash_dedup,
        )
        db.add(nova_questao)
        if questao.alternativas is not None:
            for alternativa in questao.alternativas:
                db.add(
                    Alternativa(
                        questao=nova_questao,
                        letra=alternativa.letra,
                        texto=alternativa.texto,
                        correta=alternativa.correta,
                        justificativa=None,
                    )
                )
        existentes.add(questao.hash_dedup)  # evita duplicar dentro da própria lista de entrada
        novas += 1
    db.flush()
    return novas, repetidas


def atualizar_classificacao(db: Session, questoes: list[QuestaoCurada]) -> tuple[int, int, int]:
    """Reclassifica questões já gravadas (passo 12b), sem duplicar e sem tocar no resto da linha.

    Localiza cada questão existente por `hash_dedup` e atualiza **só**
    `topico_id`/`topico_confianca`/`topico_evidencia`/`publicavel`/`motivo_nao_publicavel` — o
    texto (`comando`, `texto_apoio`, `enunciado`), o gabarito e a `origem` continuam os da
    curadoria original, sempre. Existe porque rodar `curar` de novo sobre o mesmo par com um
    classificador melhor (ex.: IA depois de ter rodado por regras) não pode virar `salvar_questoes`
    de novo — aquilo só conta repetidas, nunca atualiza uma linha existente.

    **Reclassificar nunca rebaixa (P-76).** Se a nova classificação vier **sem** tópico e a linha
    existente já tiver um, a linha fica intacta e é contada como *preservada*. Sem essa regra, uma
    rodada que caia para regras (ou cuja chamada de IA falhe — o `_classificar_um_lote` degrada em
    vez de bloquear, arquitetura §8) apaga o trabalho do classificador anterior: foi o que
    aconteceu em 23/09/2026, quando 138 publicáveis viraram 39 numa rodada só.

    Args:
        db: sessão do request/comando.
        questoes: a nova saída do curador para o mesmo caderno (mesmos `hash_dedup` de antes;
            só a classificação de tópico deve ter mudado).

    Returns:
        `(atualizadas, ignoradas, preservadas)` — *ignorada* é toda `QuestaoCurada` cujo
        `hash_dedup` não bate com nenhuma linha existente (nunca cria uma nova); *preservada* é
        toda linha que já tinha tópico e cuja nova classificação veio sem nenhum.
    """
    if not questoes:
        return 0, 0, 0

    hashes = [questao.hash_dedup for questao in questoes]
    existentes: dict[str, Questao] = {
        encontrada.hash_dedup: encontrada
        for encontrada in db.scalars(select(Questao).where(Questao.hash_dedup.in_(hashes))).all()
    }
    slugs = {questao.topico_slug for questao in questoes if questao.topico_slug is not None}
    topicos_por_slug: dict[str, Topico] = {}
    if slugs:
        for encontrado in db.scalars(select(Topico).where(Topico.slug.in_(slugs))).all():
            topicos_por_slug[encontrado.slug] = encontrado

    atualizadas = 0
    ignoradas = 0
    preservadas = 0
    for questao in questoes:
        existente = existentes.get(questao.hash_dedup)
        if existente is None:
            ignoradas += 1
            continue
        if questao.topico_slug is None and existente.topico_id is not None:
            # P-76: a nova rodada não soube classificar o que a anterior já tinha classificado.
            # Preservar é a única saída honesta — sobrescrever aqui é perder trabalho pago.
            preservadas += 1
            continue
        existente.topico = (
            topicos_por_slug.get(questao.topico_slug) if questao.topico_slug else None
        )
        existente.topico_confianca = questao.topico_confianca
        existente.topico_evidencia = questao.topico_evidencia
        existente.publicavel = questao.publicavel
        existente.motivo_nao_publicavel = questao.motivo_nao_publicavel
        atualizadas += 1
    db.flush()
    return atualizadas, ignoradas, preservadas


def contagem_por_topico(db: Session, edital_id: UUID) -> dict[UUID, int]:
    """Quantas questões publicáveis existem por tópico deste edital.

    O que fica preso a *este* edital são os **tópicos** considerados — via `TopicoEdital.edital_id`
    — não as questões contadas: `questao.topico_id` não sabe de edital nenhum, então a junção com
    `topico_edital` é o único jeito de restringir "quais tópicos valem aqui". As questões somadas
    são todas as publicáveis daquele `topico_id`, de qualquer documento/prova que as originou —
    `questao` é um pool de conteúdo global (prova pública), compartilhado por qualquer edital que
    reaproveite o mesmo tópico (premissa D: vocabulário global por `slug`). Tópico sem nenhuma
    questão publicável simplesmente não aparece no dicionário — quem exibe decide o que fazer com
    a ausência.

    Args:
        db: sessão do request.
        edital_id: chave do edital.

    Returns:
        `{topico_id: quantidade de questões com publicavel=True}`.
    """
    consulta = (
        select(TopicoEdital.topico_id, Questao.id)
        .join(Questao, Questao.topico_id == TopicoEdital.topico_id)
        .where(
            TopicoEdital.edital_id == edital_id,
            Questao.publicavel.is_(True),
            Questao.despublicada_em.is_(None),  # P-34: calibrador despublica por aqui
        )
    )
    contagem: dict[UUID, int] = {}
    for topico_id, _questao_id in db.execute(consulta).all():
        contagem[topico_id] = contagem.get(topico_id, 0) + 1
    return contagem


def proxima_questao(db: Session, usuario_id: UUID, topico_id: UUID) -> Questao | None:
    """A próxima questão publicável do tópico que este usuário nunca respondeu nem reportou.

    Premissa H: um reporte esconde a questão só para quem reportou, não para os demais alunos —
    por isso o filtro de reporte é por `usuario_id`, igual ao de resposta. A ordem é por
    `criado_em` (com `id` como desempate), nunca aleatória, para o resultado ser reproduzível em
    teste e para as questões mais antigas — em geral as primeiras curadas — saírem primeiro.

    Args:
        db: sessão do request.
        usuario_id: aluno que vai responder.
        topico_id: tópico do vocabulário global.

    Returns:
        A `Questao` mais antiga ainda disponível, ou `None` sem nenhuma sobrando.
    """
    respondidas = select(EventoEstudo.questao_id).where(
        EventoEstudo.usuario_id == usuario_id, EventoEstudo.tipo == "resposta"
    )
    reportadas = select(ReporteErro.conteudo_id).where(
        ReporteErro.usuario_id == usuario_id, ReporteErro.conteudo_tipo == "questao"
    )
    consulta = (
        select(Questao)
        .where(
            Questao.topico_id == topico_id,
            Questao.publicavel.is_(True),
            Questao.despublicada_em.is_(None),  # P-34: calibrador despublica por aqui
            Questao.id.not_in(respondidas),
            Questao.id.not_in(reportadas),
        )
        .order_by(Questao.criado_em, Questao.id)
    )
    return db.scalars(consulta).first()


def posicao_na_fila(db: Session, usuario_id: UUID, topico_id: UUID) -> tuple[int, int] | None:
    """Em que posição da fila deste tópico está o próximo item, e quantos existem ao todo.

    Mesmos filtros de `proxima_questao` (publicável, não despublicada, nem respondida nem
    reportada por este usuário) — só que aqui conta em vez de escolher. É o "questão N de M" que
    faltava na tela de resolver questão (achado do porte visual, fatia 14 §2.2): sem isso a aluna
    não sabe quanto falta na lista de hoje.

    Args:
        db: sessão do request.
        usuario_id: aluno que está respondendo.
        topico_id: tópico do vocabulário global.

    Returns:
        `(posição do próximo item, total de publicáveis)`, ambos 1-based; `None` se o tópico não
        tem nenhuma questão publicável (a tela então não mostra a contagem).
    """
    total = (
        db.scalar(
            select(func.count(Questao.id)).where(
                Questao.topico_id == topico_id,
                Questao.publicavel.is_(True),
                Questao.despublicada_em.is_(None),
            )
        )
        or 0
    )
    if total == 0:
        return None

    respondidas = select(EventoEstudo.questao_id).where(
        EventoEstudo.usuario_id == usuario_id, EventoEstudo.tipo == "resposta"
    )
    reportadas = select(ReporteErro.conteudo_id).where(
        ReporteErro.usuario_id == usuario_id, ReporteErro.conteudo_tipo == "questao"
    )
    ja_vistas = (
        db.scalar(
            select(func.count(Questao.id)).where(
                Questao.topico_id == topico_id,
                Questao.publicavel.is_(True),
                Questao.despublicada_em.is_(None),
                or_(Questao.id.in_(respondidas), Questao.id.in_(reportadas)),
            )
        )
        or 0
    )
    return min(ja_vistas + 1, total), total


def registrar_resposta(
    db: Session,
    usuario: Usuario,
    questao: Questao,
    resposta: str,
    confianca: str,
    tempo_ms: int,
    dados: dict[str, object] | None = None,
) -> EventoEstudo:
    """Grava a resposta como um `evento_estudo`; nunca altera a `questao` respondida.

    Estatística de acerto (dificuldade/discriminação estimadas) é papel da calibração, fatia
    futura — `evento_estudo` é append-only e é a única fonte da verdade sobre o que o aluno
    respondeu, quando e se acertou.

    Args:
        db: sessão do request.
        usuario: quem respondeu.
        questao: a questão respondida (só para ler o gabarito e o id; não é alterada).
        resposta: o que o aluno marcou (`"C"`/`"E"` nesta fatia).
        confianca: `"certeza"`/`"duvida"`, como o aluno declarou.
        tempo_ms: tempo gasto na questão, em milissegundos.
        dados: o JSON livre de `evento_estudo.dados` (V5); hoje só o fio da memória grava aqui
            (`bloco_topico_id` e, quando o item é intercalado, `fio_motivo`/
            `fio_origem_topico_id`) — `None` quando a rota não passa nada.

    Returns:
        O `EventoEstudo` gravado.
    """
    evento = EventoEstudo(
        usuario_id=usuario.id,
        ocorrido_em=agora_utc(),
        tipo="resposta",
        questao_id=questao.id,
        acertou=resposta == questao.gabarito,
        resposta=resposta,
        tempo_ms=tempo_ms,
        confianca_declarada=confianca,
        dados=dados,
    )
    db.add(evento)
    db.flush()
    return evento


def registrar_reporte(db: Session, usuario: Usuario, questao: Questao, motivo: str) -> ReporteErro:
    """Grava o reporte de erro e o evento correspondente; a questão continua publicada.

    Despublicar por reporte é papel do calibrador (fatia 8) — aqui a questão só some de
    `proxima_questao` para quem reportou (premissa H); os demais alunos continuam recebendo-a.

    Args:
        db: sessão do request.
        usuario: quem reportou.
        questao: a questão reportada.
        motivo: o texto livre do reporte.

    Returns:
        O `ReporteErro` gravado, com `status="aberto"`.
    """
    reporte = ReporteErro(
        usuario_id=usuario.id,
        conteudo_tipo="questao",
        conteudo_id=questao.id,
        motivo=motivo,
        status="aberto",
    )
    db.add(reporte)
    db.add(
        EventoEstudo(
            usuario_id=usuario.id,
            ocorrido_em=agora_utc(),
            tipo="reporte",
            questao_id=questao.id,
        )
    )
    db.flush()
    return reporte


def questoes_publicaveis_do_topico(db: Session, topico_slug: str) -> list[Questao]:
    """As questões publicáveis de um tópico, ordenadas por criação (determinístico).

    Usado pelo comando `motor.justificar` para escolher o universo de uma rodada com
    `--topico`. Como `contagem_por_topico`, ignora o edital de origem (o tópico é vocabulário
    global) — a única restrição é `publicavel=True`, o mesmo gate de `proxima_questao`.

    Args:
        db: sessão do request/comando.
        topico_slug: slug do tópico.

    Returns:
        As `Questao` publicáveis desse tópico, na ordem de `criado_em`/`id`; lista vazia se o
        tópico não existir ou não tiver nenhuma publicável.
    """
    consulta = (
        select(Questao)
        .join(Topico, Questao.topico_id == Topico.id)
        .where(
            Topico.slug == topico_slug,
            Questao.publicavel.is_(True),
            Questao.despublicada_em.is_(None),  # P-34: calibrador despublica por aqui
        )
        .order_by(Questao.criado_em, Questao.id)
    )
    return list(db.scalars(consulta).all())


def gravar_justificativa_certo_errado(
    db: Session, questao: Questao, *, certo: str, errado: str
) -> None:
    """Grava as duas justificativas de um item certo/errado já aprovado pelo validador mecânico.

    Args:
        db: sessão do request/comando.
        questao: a questão já publicável cujo par de justificativas foi aprovado.
        certo: o texto de `justificativa_certo` (`dominio.justificativa.montar_texto` das
            afirmações aprovadas).
        errado: o texto de `justificativa_errado`.
    """
    questao.justificativa_certo = certo
    questao.justificativa_errado = errado
    db.flush()


def gravar_justificativa_alternativas(
    db: Session, questao: Questao, textos_por_letra: dict[str, str]
) -> None:
    """Grava a justificativa de cada alternativa de uma questão de múltipla escolha já aprovada.

    Args:
        db: sessão do request/comando.
        questao: a questão de múltipla escolha cujas justificativas foram aprovadas.
        textos_por_letra: `{letra: texto}` (`dominio.justificativa.montar_texto` das afirmações
            de cada alternativa); uma letra sem entrada aqui não é tocada.
    """
    alternativas = db.scalars(select(Alternativa).where(Alternativa.questao_id == questao.id)).all()
    for alternativa in alternativas:
        texto = textos_por_letra.get(alternativa.letra)
        if texto is not None:
            alternativa.justificativa = texto
    db.flush()


def topicos_vistos(db: Session, usuario_id: UUID, edital_id: UUID) -> set[UUID]:
    """Os tópicos deste edital com pelo menos uma resposta deste usuário (premissa N).

    É o que faz o "0 de 36" da página do concurso (V2) contar de verdade a partir da V3: um
    tópico entra no conjunto assim que o aluno responde à primeira questão dele.

    Args:
        db: sessão do request.
        usuario_id: aluno.
        edital_id: chave do edital (o tópico é vocabulário global; o edital decide quais tópicos
            valem para este conjunto).

    Returns:
        Conjunto de `topico_id`; vazio se nada foi respondido ainda.
    """
    consulta = (
        select(TopicoEdital.topico_id)
        .join(Questao, Questao.topico_id == TopicoEdital.topico_id)
        .join(EventoEstudo, EventoEstudo.questao_id == Questao.id)
        .where(
            TopicoEdital.edital_id == edital_id,
            EventoEstudo.usuario_id == usuario_id,
            EventoEstudo.tipo == "resposta",
        )
        .distinct()
    )
    return set(db.scalars(consulta).all())


def salvar_questao_inedita(
    db: Session,
    *,
    topico_id: UUID,
    item: QuestaoGerada,
    publicavel: bool,
    motivo_nao_publicavel: str | None,
    validador_versao: str,
    regra_prova: RegraProva,
) -> Questao:
    """Grava uma inédita do `gerador-de-questao` — aprovada ou reprovada, sempre (RF-28).

    `origem`/`documento_id` ficam `None` (inédita não tem procedência de prova, ao contrário de
    `salvar_questoes`); `inedita=True`; `justificativa_certo`/`justificativa_errado` já vêm
    preenchidos pelo gerador (ao contrário de `salvar_questoes`, cuja questão nasce sem
    justificativa — quem preenche depois é `motor.justificar`). Não deduplica por `hash_dedup`:
    cada chamada ao gerador já corresponde a um item novo do plano do lote; deduplicar aqui
    esconderia uma divergência que `dominio.questao_inedita.conferir_lote` precisa enxergar.

    Args:
        db: sessão do comando (faz `add`/`flush`; o `commit` é de quem chama).
        topico_id: o tópico desta inédita.
        item: a `QuestaoGerada` do agente `gerador-de-questao`.
        publicavel: o veredito de `dominio.validacao_questao.julgar` (`Veredito.aprovado`).
        motivo_nao_publicavel: `"; ".join(Veredito.motivos)` quando `publicavel` é `False`;
            `None` quando `True`.
        validador_versao: `Veredito.validador_versao` desta tentativa.
        regra_prova: a regra de correção a registrar (do DNA do concurso, quando conhecida, ou
            um placeholder declarado — este módulo não decide qual; só grava o que recebe).

    Returns:
        A `Questao` recém-criada (e as `Alternativa`, se `item.alternativas` não for `None`).
    """
    questao = Questao(
        adapter="concursos",
        banca=item.banca_alvo,
        tipo_item=item.tipo_item,
        comando=item.comando,
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado=item.enunciado,
        gabarito_preliminar=None,
        gabarito=item.gabarito,
        gabarito_status="definitivo",
        publicavel=publicavel,
        motivo_nao_publicavel=motivo_nao_publicavel,
        regra_prova=regra_prova.model_dump(mode="json"),
        topico_id=topico_id,
        topico_confianca="alta",
        topico_evidencia=f"gerada pelo gerador-de-questao para {item.topico_slug}",
        origem=None,
        inedita=True,
        documento_id=None,
        hash_dedup=hash_dedup(f"{item.topico_slug}:{item.mecanismo}:{item.enunciado}"),
        validada_em=agora_utc(),
        validador_versao=validador_versao,
        justificativa_certo=item.justificativa_certo,
        justificativa_errado=item.justificativa_errado,
    )
    db.add(questao)
    if item.alternativas is not None:
        for alternativa in item.alternativas:
            db.add(
                Alternativa(
                    questao=questao,
                    letra=alternativa.letra,
                    texto=alternativa.texto,
                    correta=alternativa.letra == item.gabarito,
                    justificativa=None,
                )
            )
    db.flush()
    return questao
