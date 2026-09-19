"""Repositório das páginas públicas: as consultas que decidem quais páginas existem (fatia 13).

O que é: `candidatas_familia_a` (tópico × banca, aplicando o corte de
`dominio.pagina_publica.cabe_em_pagina` e a canonicalização por equivalência — Ruling 49/
ADR-0041), `candidatas_familia_c` (uma pergunta de formato por banca, a partir de
`dna_concurso.regra_correcao`) e `candidatas_familia_d` (o verticalizado público, só para
concursos com `data_prova` conhecida — a família B, que traria o catálogo completo, é da fatia
1b). As três devolvem listas de "página pronta" (metadados + conteúdo), na mesma consulta que
`api/publico.py` usa para servir uma página e para montar `sitemap.xml`/`robots.txt` — nunca duas
fontes de verdade sobre quais páginas existem (plano §3: "sitemap que lista página inexistente é
erro de indexação auto-infligido"). Só leitura: nenhuma função aqui grava nada.

**Limite conhecido (registrado em `docs/PENDENCIAS.md`):** a família A só considera `Questao.banca`
(a proveniência real e medida da questão) como fonte da banca do endereço
`/o-que-cai/{banca}/...` — um tópico com dossiê publicado mas nenhuma questão publicável fica de
fora nesta rodada, porque a única banca disponível para ele viria do `Concurso` do tenant que
subiu o edital, e nada no modelo de dados distingue um concurso real de um concurso de fixture de
teste (ex.: o edital fictício da Fase 4 usado no piloto). Publicar esse nome como se fosse uma
banca de verdade seria inventar procedência (regra 2 do playbook §3). Famílias C e D não têm essa
guarda (usam `Concurso`/`dna_concurso` diretamente) — mesma ressalva, registrada como pendência
em vez de resolvida aqui.

Quando ler: ao mudar o corte de qualquer família, ao investigar por que uma página não aparece no
sitemap, ou ao entender por que duas páginas equivalentes viraram uma canônica.
"""

from typing import Final
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import (
    Concurso,
    DnaConcursoRegistro,
    DossieTopico,
    Questao,
    Topico,
)
from aprovaos.dados.repositorio_edital import (
    MateriaVerticalizada,
    edital_atual,
    verticalizado,
)
from aprovaos.dados.repositorio_topico_relacao import topicos_equivalentes
from aprovaos.dominio.dna import DnaConcurso
from aprovaos.dominio.edital import slug_materia
from aprovaos.dominio.pagina_publica import (
    ajustar_descricao,
    cabe_em_pagina,
    montar_titulo_de_topico,
)

#: Valor de `concurso.origem` que pode chegar ao público (P-62, migração 0017). Concurso de
#: fixture de teste **nunca** vira página: publicá-lo seria apresentar como medido um número
#: que um modelo inventou — a ADR-0036 com plateia.
ORIGEM_REAL: Final = "real"

#: Quantas perguntas de formato (família C) o catálogo cobre nesta fatia — só a mais medida e
#: mais buscada (playbook §8, "cebraspe desconta erro"); o catálogo cresce conforme o uso real
#: (P-12) mostrar quais perguntas valem a pena, não por adivinhação.
PERGUNTA_DESCONTO_POR_ERRO = "desconto-por-erro"


class QuestaoPublica(BaseModel):
    """Uma questão como aparece numa página pública: origem completa, nunca o gabarito.

    Attributes:
        banca: banca examinadora que produziu a questão.
        orgao: órgão do concurso original da questão.
        ano: ano do concurso original.
        numero_item: número do item impresso no caderno original.
        enunciado: o texto da questão, como a banca imprimiu.
    """

    banca: str
    orgao: str
    ano: int
    numero_item: int
    enunciado: str


class FontePublica(BaseModel):
    """Uma fonte de dossiê no formato que a macro `citacao_legal` (`_macros.html`) espera."""

    dispositivo_rotulo: str
    dispositivo_texto: str | None
    dispositivo_url: str | None


class PaginaTopicoBanca(BaseModel):
    """Uma página da família A, pronta para o template (`publico/topico.html`).

    Attributes:
        caminho: endereço da página.
        titulo: `<title>`.
        descricao: `<meta name="description">`.
        h1: título visível da página.
        canonica: caminho da página canônica, quando esta é equivalente a outra de maior
            cobertura medida (Ruling 49); `None` quando esta já é a canônica.
        atualizada_em_iso: `atualizada_em` em ISO 8601 (`YYYY-MM-DD`), para `Last-Modified`/
            `sitemap.xml` sem reimportar `datetime` no template.
        banca: banca das questões mostradas.
        materia: matéria do tópico.
        topico_nome: nome do tópico.
        n_questoes: quantas questões publicáveis sustentam a página.
        tem_dossie: se este tópico (diretamente, sem equivalência) tem dossiê publicado.
        dossie_paragrafos: parágrafos do dossiê (`DossieTopico.conteudo` já dividido); vazio sem
            dossiê direto.
        dossie_fontes: as fontes do dossiê, no formato de `citacao_legal`; vazio sem dossiê.
        questoes: as questões publicáveis desta banca/tópico, sem gabarito.
    """

    caminho: str
    titulo: str
    descricao: str
    h1: str
    canonica: str | None
    atualizada_em_iso: str
    banca: str
    materia: str
    topico_nome: str
    n_questoes: int
    tem_dossie: bool
    dossie_paragrafos: list[str]
    dossie_fontes: list[FontePublica]
    questoes: list[QuestaoPublica]


class PaginaDuvida(BaseModel):
    """Uma página da família C, pronta para o template (`publico/duvida.html`)."""

    caminho: str
    titulo: str
    descricao: str
    h1: str
    atualizada_em_iso: str
    pergunta: str
    banca: str
    resposta: str
    fonte: str


class PaginaVerticalizado(BaseModel):
    """Uma página da família D, pronta para o template (`publico/verticalizado.html`)."""

    caminho: str
    titulo: str
    descricao: str
    h1: str
    atualizada_em_iso: str
    orgao: str
    cargo: str
    banca: str
    ano: int
    materias: list[MateriaVerticalizada]


def _grupo_equivalente(db: Session, topico_id: UUID) -> set[UUID]:
    """O componente conexo de `topico_id` no grafo de equivalência plena (busca em largura)."""
    vistos = {topico_id}
    fila = [topico_id]
    while fila:
        atual = fila.pop()
        for vizinho in topicos_equivalentes(db, atual):
            if vizinho not in vistos:
                vistos.add(vizinho)
                fila.append(vizinho)
    return vistos


def _dossie_direto(db: Session, topico_id: UUID) -> DossieTopico | None:
    """A versão mais recente de `dossie_topico` gravada **diretamente** sob `topico_id`.

    Ao contrário de `repositorio_dossie.dossie_mais_recente_do_topico`, não segue equivalência —
    o corte da família A é por página (`topico_id`, `banca`), e o dossiê de um tópico equivalente
    pertence à página *dele*, não a esta.
    """
    return db.scalars(
        select(DossieTopico)
        .where(DossieTopico.topico_id == topico_id)
        .order_by(DossieTopico.versao.desc())
        .limit(1)
    ).first()


def _questoes_do_topico_banca(db: Session, topico_id: UUID, banca: str) -> list[Questao]:
    """As questões publicáveis (e vivas) de `topico_id` com `banca`, da mais antiga à mais nova."""
    consulta = (
        select(Questao)
        .where(
            Questao.topico_id == topico_id,
            Questao.banca == banca,
            Questao.publicavel.is_(True),
            Questao.despublicada_em.is_(None),
        )
        .order_by(Questao.criado_em, Questao.id)
    )
    return list(db.scalars(consulta).all())


def _origem_de(questao: Questao) -> tuple[str, int]:
    """`(orgao, ano)` da `Questao.origem` (JSON); `("desconhecido", 0)` se ausente — defensivo."""
    origem = questao.origem or {}
    orgao = str(origem.get("orgao") or "desconhecido")
    ano = int(origem.get("ano") or 0)
    return orgao, ano


def candidatas_familia_a(db: Session) -> list[PaginaTopicoBanca]:
    """Toda página da família A que passa do corte hoje, já com a canonicalização resolvida.

    Args:
        db: sessão de banco (só leitura).

    Returns:
        Lista ordenada (por caminho) de `PaginaTopicoBanca` — inclui tanto a canônica quanto as
        equivalentes (que carregam `canonica` preenchida); quem monta `sitemap.xml` filtra
        `canonica is None`.
    """
    contagens = db.execute(
        select(Questao.topico_id, Questao.banca, func.count(Questao.id))
        .where(
            Questao.publicavel.is_(True),
            Questao.despublicada_em.is_(None),
            Questao.topico_id.is_not(None),
        )
        .group_by(Questao.topico_id, Questao.banca)
    ).all()
    contagem_por_chave: dict[tuple[UUID, str], int] = {
        (topico_id, banca): quantidade for topico_id, banca, quantidade in contagens if topico_id
    }
    if not contagem_por_chave:
        return []

    topico_ids = {topico_id for topico_id, _ in contagem_por_chave}
    topicos = {t.id: t for t in db.scalars(select(Topico).where(Topico.id.in_(topico_ids))).all()}

    aprovados: dict[tuple[UUID, str], int] = {}
    for (topico_id, banca), n in contagem_por_chave.items():
        tem_dossie = _dossie_direto(db, topico_id) is not None
        if cabe_em_pagina(n, tem_dossie):
            aprovados[(topico_id, banca)] = n

    # Canonicalização (Ruling 49): só faz sentido comparar cobertura dentro da MESMA banca — duas
    # bancas diferentes sobre o mesmo assunto de direito nunca são o mesmo conteúdo.
    canonico_de: dict[tuple[UUID, str], UUID] = {}
    por_banca: dict[str, set[UUID]] = {}
    for topico_id, banca in aprovados:
        por_banca.setdefault(banca, set()).add(topico_id)
    for banca, ids in por_banca.items():
        ja_agrupados: set[UUID] = set()
        for topico_id in sorted(ids, key=str):
            if topico_id in ja_agrupados:
                continue
            grupo = _grupo_equivalente(db, topico_id) & ids
            ja_agrupados |= grupo
            if len(grupo) <= 1:
                continue
            canonico = max(grupo, key=lambda tid: (aprovados[(tid, banca)], str(tid)))
            for membro in grupo:
                if membro != canonico:
                    canonico_de[(membro, banca)] = canonico

    def _caminho(topico_id: UUID, banca: str) -> str:
        topico = topicos[topico_id]
        return f"/o-que-cai/{slug_materia(banca)}/{slug_materia(topico.materia)}/{topico.slug}"

    paginas: list[PaginaTopicoBanca] = []
    for (topico_id, banca), n in aprovados.items():
        topico = topicos[topico_id]
        dossie = _dossie_direto(db, topico_id)
        questoes_orm = _questoes_do_topico_banca(db, topico_id, banca)
        questoes = []
        for q in questoes_orm:
            orgao, ano = _origem_de(q)
            questoes.append(
                QuestaoPublica(
                    banca=q.banca,
                    orgao=orgao,
                    ano=ano,
                    numero_item=int((q.origem or {}).get("numero_item") or 0),
                    enunciado=q.enunciado,
                )
            )
        dossie_paragrafos = [
            p for p in (dossie.conteudo.split("\n\n") if dossie else []) if p.strip()
        ]
        dossie_fontes = [
            FontePublica(
                dispositivo_rotulo=str(f.get("citacao_canonica") or ""),
                dispositivo_texto=f.get("trecho"),
                dispositivo_url=f.get("url"),
            )
            for f in (dossie.fontes if dossie else [])
        ]
        datas = [q.atualizado_em for q in questoes_orm]
        if dossie is not None:
            datas.append(dossie.atualizado_em)
        atualizada_em = max(datas).date() if datas else topico.atualizado_em.date()

        descricao_base = f"{n} questão classificada" if n == 1 else f"{n} questões classificadas"
        descricao_base = f"{descricao_base} de {topico.materia} sobre {topico.nome}"
        if dossie is not None:
            descricao_base += ", com o dossiê jurídico do assunto (trecho literal e fonte)"
        descricao_base += "."

        canonica_id = canonico_de.get((topico_id, banca))
        canonica_caminho = _caminho(canonica_id, banca) if canonica_id is not None else None

        pagina = PaginaTopicoBanca(
            caminho=_caminho(topico_id, banca),
            titulo=montar_titulo_de_topico(topico.materia, topico.nome, banca, n),
            descricao=ajustar_descricao(descricao_base),
            h1=topico.nome,
            canonica=canonica_caminho,
            atualizada_em_iso=atualizada_em.isoformat(),
            banca=banca,
            materia=topico.materia,
            topico_nome=topico.nome,
            n_questoes=n,
            tem_dossie=dossie is not None,
            dossie_paragrafos=dossie_paragrafos,
            dossie_fontes=dossie_fontes,
            questoes=questoes,
        )
        paginas.append(pagina)

    paginas.sort(key=lambda p: p.caminho)
    return paginas


def pagina_topico_banca(
    db: Session, *, banca_slug: str, materia_slug: str, topico_slug: str
) -> PaginaTopicoBanca | None:
    """A página da família A no endereço exato, ou `None` sem página nesse endereço.

    Confere os três segmentos do caminho (não só o `topico_slug`, globalmente único): um
    `banca_slug`/`materia_slug` que não bate com o que `candidatas_familia_a` geraria para este
    tópico é um endereço que nunca existiu — 404, não um redirecionamento silencioso, para não
    indexar duas URLs para o mesmo conteúdo.

    Args:
        db: sessão de banco (só leitura).
        banca_slug: segmento de banca da URL.
        materia_slug: segmento de matéria da URL.
        topico_slug: segmento de tópico da URL (`Topico.slug`).

    Returns:
        A `PaginaTopicoBanca` cujo `caminho` bate exatamente com os três segmentos; `None` caso
        contrário.
    """
    caminho = f"/o-que-cai/{banca_slug}/{materia_slug}/{topico_slug}"
    for pagina in candidatas_familia_a(db):
        if pagina.caminho == caminho:
            return pagina
    return None


def candidatas_familia_c(db: Session) -> list[PaginaDuvida]:
    """As páginas da família C hoje: uma por banca com `regra_correcao.anula_por_erro` medida.

    Args:
        db: sessão de banco (só leitura).

    Returns:
        Lista ordenada por caminho; uma banca com `anula_por_erro == "desconhecido"` ainda gera
        página (a resposta é "ainda não medimos" — regra 2 do playbook: nunca inventa o número
        que falta), porque a pergunta em si já é buscada mesmo sem resposta certa.
    """
    # A versão mais recente por concurso é decidida em Python (não por subconsulta correlacionada
    # — o volume aqui é "quantos concursos existem", nunca alto o bastante para justificar o
    # SQL mais complicado): busca todo registro e fica só com o de maior `versao` por concurso.
    registros = db.execute(
        select(Concurso, DnaConcursoRegistro)
        .join(DnaConcursoRegistro)
        .where(Concurso.origem == ORIGEM_REAL)
    ).all()
    mais_recente_por_concurso: dict[UUID, tuple[Concurso, DnaConcursoRegistro]] = {}
    for concurso, registro in registros:
        atual = mais_recente_por_concurso.get(concurso.id)
        if atual is None or registro.versao > atual[1].versao:
            mais_recente_por_concurso[concurso.id] = (concurso, registro)

    # Uma pergunta por banca — com mais de um concurso da mesma banca, fica o mais recente
    # (`Concurso.criado_em` desc); agregar as duas medições é trabalho de quando isso acontecer
    # de verdade, não antes (nenhum caso hoje).
    por_banca: dict[str, tuple[Concurso, DnaConcursoRegistro]] = {}
    for concurso, registro in sorted(
        mais_recente_por_concurso.values(), key=lambda par: par[0].criado_em
    ):
        por_banca[concurso.banca] = (concurso, registro)

    paginas: list[PaginaDuvida] = []
    for banca, (concurso, registro) in por_banca.items():
        dna = DnaConcurso.model_validate(registro.conteudo)
        anula = dna.regra_correcao.anula_por_erro
        fonte = f"edital {dna.concurso.edital} — {concurso.orgao} ({dna.regra_correcao.fonte})"
        if anula == "desconhecido":
            resposta = (
                f"Ainda não medimos essa regra para {banca}: o edital consultado não deixou "
                "claro se uma resposta errada anula uma certa. Assim que um edital desta banca "
                "trouxer essa informação, esta página é atualizada."
            )
        elif anula:
            resposta = (
                f"Sim — no edital medido de {banca}, uma resposta errada anula uma certa ({fonte})."
            )
        else:
            resposta = (
                f"Não — no edital medido de {banca}, uma resposta errada não anula uma certa "
                f"({fonte})."
            )
        pergunta = f"A banca {banca} desconta questão errada?"
        caminho = f"/duvidas/{PERGUNTA_DESCONTO_POR_ERRO}-{slug_materia(banca)}"
        paginas.append(
            PaginaDuvida(
                caminho=caminho,
                titulo=f"{pergunta} | AprovaOS",
                descricao=ajustar_descricao(resposta),
                h1=pergunta,
                atualizada_em_iso=registro.atualizado_em.date().isoformat(),
                pergunta=pergunta,
                banca=banca,
                resposta=resposta,
                fonte=fonte,
            )
        )
    paginas.sort(key=lambda p: p.caminho)
    return paginas


def pagina_duvida(db: Session, *, slug_pergunta: str) -> PaginaDuvida | None:
    """A página da família C no endereço exato, ou `None` sem página nesse endereço."""
    caminho = f"/duvidas/{slug_pergunta}"
    for pagina in candidatas_familia_c(db):
        if pagina.caminho == caminho:
            return pagina
    return None


def candidatas_familia_d(db: Session) -> list[PaginaVerticalizado]:
    """As páginas da família D hoje: verticalizado público de todo concurso com `data_prova`.

    Args:
        db: sessão de banco (só leitura).

    Returns:
        Lista ordenada por caminho; um concurso sem `data_prova` conhecida (não é o caso raro —
        é o caso de metade da base hoje) fica de fora, porque o endereço
        `/verticalizado/{orgao}-{ano}` exige o ano e a regra 2 do playbook proíbe inventá-lo.
    """
    concursos = list(
        db.scalars(
            select(Concurso).where(Concurso.data_prova.is_not(None), Concurso.origem == ORIGEM_REAL)
        ).all()
    )
    paginas: list[PaginaVerticalizado] = []
    for concurso in concursos:
        edital = edital_atual(db, concurso.id)
        if edital is None or concurso.data_prova is None:
            continue
        ano = concurso.data_prova.year
        materias = verticalizado(db, edital.id)
        caminho = f"/verticalizado/{slug_materia(concurso.orgao)}-{ano}"
        titulo = f"Edital verticalizado — {concurso.orgao} ({ano}) | AprovaOS"
        h1 = f"Edital verticalizado de {concurso.orgao} — {concurso.cargo} ({ano})"
        descricao = ajustar_descricao(
            f"O conteúdo programático de {concurso.orgao} ({ano}) verticalizado por matéria e "
            f"tópico, direto do edital (banca {concurso.banca})."
        )
        atualizada_em = max(edital.atualizado_em, concurso.atualizado_em).date()
        paginas.append(
            PaginaVerticalizado(
                caminho=caminho,
                titulo=titulo,
                descricao=descricao,
                h1=h1,
                atualizada_em_iso=atualizada_em.isoformat(),
                orgao=concurso.orgao,
                cargo=concurso.cargo,
                banca=concurso.banca,
                ano=ano,
                materias=materias,
            )
        )
    paginas.sort(key=lambda p: p.caminho)
    return paginas


def pagina_verticalizado(db: Session, *, slug_orgao_ano: str) -> PaginaVerticalizado | None:
    """A página da família D no endereço exato, ou `None` sem página nesse endereço."""
    caminho = f"/verticalizado/{slug_orgao_ano}"
    for pagina in candidatas_familia_d(db):
        if pagina.caminho == caminho:
            return pagina
    return None
