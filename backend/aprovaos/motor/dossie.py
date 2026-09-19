"""O comando que monta e grava o dossiê de um tópico — generalizado por receita (fatia 4).

O que é: `construir_dossie(db, topico_slug, hoje=None)`, dirigido pela receita cadastrada em
`RECEITAS[topico_slug]` (pedidos de dispositivo de norma + pedidos de súmula, curados à mão —
ver `docs/fatias/4-dossies-de-topico.md` §3 para o porquê de cada dispositivo/súmula escolhido).
Generaliza a versão anterior desta fatia (uma função hardcoded por tópico,
`construir_dossie_improbidade`, só para Lei 8.429/1992): agora é uma linha de dado por tópico,
não uma função por tópico — mesma disciplina de sempre (todo pedido vira fonte com trecho real
ou lacuna declarada; `dominio.dossie.montar_dossie` continua sem rede, sem LLM).

`topicos_de_maior_peso(db, edital_id, limite)` é o critério "de maior peso" desta fatia (plano
§1.2): nº de questões **publicáveis** por tópico do edital, descendente — peso medido, não
declarado (o edital não tem peso por tópico, só peso uniforme por matéria, uma lacuna já
registrada desde a V2/P-39).

`main()` roda um tópico (`--topico`, repetível) ou os `--top` tópicos de maior peso de um edital
(`--edital-id`), grava (salvo `--dry-run`) e imprime o relatório — inclusive os tópicos do
ranking sem receita cadastrada ("sem receita"), nunca escondidos. Nenhuma execução acontece em
import.

Quando ler: ao acrescentar uma receita nova, trocar o critério de peso, ou investigar por que um
tópico do ranking não gerou dossiê.
"""

import argparse
from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.config import Configuracoes, obter_configuracoes
from aprovaos.dados.conexao import criar_engine, criar_fabrica_sessao
from aprovaos.dados.modelos import DossieTopico, Questao, Topico, TopicoEdital
from aprovaos.dados.repositorio_dossie import salvar_dossie
from aprovaos.dominio.dossie import ConteudoDossie, PedidoDispositivo, PedidoSumula, montar_dossie
from aprovaos.dominio.erros import TopicoNaoEncontrado
from aprovaos.motor.ancorar import html_offline_da_norma
from aprovaos.motor.fontes.planalto import CATALOGO
from aprovaos.motor.fontes.sumulas_offline import resolver_sumulas_offline

_LEI_8429 = "lei-8429-1992"
_LEI_13105 = "lei-13105-2015"
_CF = "cf-1988"


class ReceitaDossie(BaseModel):
    """A curadoria manual de um dossiê: os dispositivos de norma e as súmulas que ele pede.

    Attributes:
        pedidos: dispositivos de norma pedidos (`dominio.dossie.PedidoDispositivo`).
        sumulas: súmulas pedidas (`dominio.dossie.PedidoSumula`); vazia quando o tópico ainda
            não tem jurisprudência curada.
    """

    pedidos: list[PedidoDispositivo]
    sumulas: list[PedidoSumula] = Field(default_factory=list)


RECEITAS: dict[str, ReceitaDossie] = {
    "dir-adm-06-improbidade-administrativa": ReceitaDossie(
        pedidos=[
            PedidoDispositivo(norma=_LEI_8429, artigo="1"),
            PedidoDispositivo(norma=_LEI_8429, artigo="1", paragrafo="1"),  # rol fechado (9-11)
            PedidoDispositivo(norma=_LEI_8429, artigo="1", paragrafo="2"),  # definição de dolo
            PedidoDispositivo(norma=_LEI_8429, artigo="1", paragrafo="3"),  # sem dolo, sem ato
            PedidoDispositivo(norma=_LEI_8429, artigo="1", paragrafo="8"),  # divergência não é
            PedidoDispositivo(norma=_LEI_8429, artigo="2"),  # quem é agente público
            PedidoDispositivo(norma=_LEI_8429, artigo="3"),  # particular que induz dolosamente
            # arts. 9, 10 e 11 eram lacuna (título de Seção/Capítulo em Title Case entre eles)
            # até a P-40 tratar as quatro estruturas em `dominio.legislacao` — resolvem como
            # fonte desde então.
            PedidoDispositivo(norma=_LEI_8429, artigo="9"),  # enriquecimento ilícito
            PedidoDispositivo(norma=_LEI_8429, artigo="10"),  # prejuízo ao erário
            PedidoDispositivo(norma=_LEI_8429, artigo="11"),  # atentado aos princípios
            # art. 17 continua sendo pedido (rito único + § 4º-A, sufixo de letra tratado pela
            # P-40) mas hoje é lacuna de novo, por um motivo real e não relacionado a nenhum
            # heurístico deste código: o § 6º-A do Planalto tem um parêntese não fechado antes
            # da anotação "(Incluído pela Lei nº 14.230, de 2021)" — a rede de segurança apertada
            # na revisão de 19/09/2026 (I6, P-61) recusa aceitar esse dispositivo truncado como
            # se fosse completo. Ver `test_motor_dossie.py
            # ::test_artigo_17_volta_a_ser_lacuna_por_anomalia_real_no_6a_nao_pelo_titulo`.
            PedidoDispositivo(norma=_LEI_8429, artigo="17"),  # rito único + § 4º-A (foro)
            PedidoDispositivo(norma=_LEI_8429, artigo="23"),  # prescrição
        ],
        sumulas=[
            # STJ 651: demissão administrativa independe de condenação judicial.
            PedidoSumula(chave="stj-sumula-651", tribunal="stj", numero=651),
            # STJ 634: particular tem o mesmo prazo prescricional do agente público.
            PedidoSumula(chave="stj-sumula-634", tribunal="stj", numero=634),
        ],
    ),
    "dir-con-02-direitos-garantias": ReceitaDossie(
        pedidos=[
            PedidoDispositivo(norma=_CF, artigo="5"),  # caput — igualdade formal
            PedidoDispositivo(norma=_CF, artigo="5", inciso="XXXVI"),  # ato jurídico perfeito
            PedidoDispositivo(norma=_CF, artigo="5", inciso="LIV"),  # devido processo legal
            PedidoDispositivo(norma=_CF, artigo="5", inciso="LV"),  # contraditório/ampla defesa
            PedidoDispositivo(norma=_CF, artigo="5", paragrafo="1"),  # aplicação imediata
            PedidoDispositivo(norma=_CF, artigo="5", paragrafo="2"),  # rol não exaustivo
        ],
        sumulas=[
            # SV 1: ato jurídico perfeito × termo de adesão do FGTS (liga direto ao art. 5º XXXVI).
            PedidoSumula(chave="stf-sv-1", tribunal="stf", numero=1, vinculante=True),
            # SV 11: uso de algemas — liga a devido processo/dignidade (art. 5º LIV/LV).
            PedidoSumula(chave="stf-sv-11", tribunal="stf", numero=11, vinculante=True),
        ],
    ),
    "dir-pro-civ-05-recursos-apelacao": ReceitaDossie(
        pedidos=[
            PedidoDispositivo(norma=_LEI_13105, artigo="1009"),  # cabimento da apelação
            PedidoDispositivo(norma=_LEI_13105, artigo="1010"),  # requisitos da petição
            PedidoDispositivo(norma=_LEI_13105, artigo="1015"),  # agravo de instrumento — rol
            PedidoDispositivo(norma=_LEI_13105, artigo="1022"),  # embargos de declaração—cabimento
            PedidoDispositivo(norma=_LEI_13105, artigo="1023"),  # embargos — prazo
            PedidoDispositivo(norma=_LEI_13105, artigo="1024"),  # embargos — julgamento
            # era lacuna proposital: "Seção I Do Recurso Ordinário" em Title Case entre 1.025 e
            # 1.026 (achado desta fatia, §2 do plano) — a P-40 tratou título em Title Case em
            # `dominio.legislacao`, resolve como fonte desde então.
            PedidoDispositivo(norma=_LEI_13105, artigo="1026"),
        ],
        sumulas=[
            # STJ 98: embargos com propósito de prequestionamento não são protelatórios.
            PedidoSumula(chave="stj-sumula-98", tribunal="stj", numero=98),
            # STJ 347: apelação do réu independe de prisão.
            PedidoSumula(chave="stj-sumula-347", tribunal="stj", numero=347),
        ],
    ),
    "dir-pro-civ-03-atos-processuais": ReceitaDossie(
        pedidos=[
            PedidoDispositivo(norma=_LEI_13105, artigo="188"),  # liberdade de forma
            PedidoDispositivo(norma=_LEI_13105, artigo="218"),  # prazos — regra geral
            PedidoDispositivo(norma=_LEI_13105, artigo="219"),  # só dias úteis
            PedidoDispositivo(norma=_LEI_13105, artigo="224"),  # contagem, exclui dia do começo
            PedidoDispositivo(norma=_LEI_13105, artigo="231"),  # termo inicial por comunicação
        ],
        sumulas=[
            # STJ 216: tempestividade é aferida pelo protocolo, não pela postagem no correio.
            PedidoSumula(chave="stj-sumula-216", tribunal="stj", numero=216),
        ],
    ),
}
"""Receitas curadas à mão nesta fatia (`docs/fatias/4-dossies-de-topico.md` §3) — os 4 tópicos
de maior peso medido do edital fictício (Cascavel/Unioeste, ADR-0027) com norma catalogada e
súmula real disponível. `dir-adm-03-poderes-administrativos` (5º do ranking, doutrina sem um
dispositivo único óbvio) fica de propósito sem receita — `main()` reporta isso, não pula em
silêncio (§3/§4 do plano)."""


SLUG_IMPROBIDADE = "dir-adm-06-improbidade-administrativa"
"""Alias estável para quem ligou nesta constante antes da generalização (`motor.justificar`,
`motor.ligar_por_topico`, seus testes) — continua sendo o tópico-piloto da fundação jurídica."""


def _buscar_topico(db: Session, slug: str) -> Topico:
    """Busca o `Topico` por `slug`; levanta `TopicoNaoEncontrado` em vez de criá-lo."""
    topico = db.scalars(select(Topico).where(Topico.slug == slug)).first()
    if topico is None:
        raise TopicoNaoEncontrado(
            f"tópico {slug!r} não está cadastrado — rode o parser de edital antes do dossiê."
        )
    return topico


def construir_dossie(
    db: Session, topico_slug: str, *, hoje: date | None = None
) -> tuple[DossieTopico, ConteudoDossie]:
    """Monta e grava o dossiê de `topico_slug`, pela receita cadastrada em `RECEITAS`.

    Args:
        db: sessão de banco (precisa ter o `Topico` de `topico_slug` já cadastrado).
        topico_slug: o tópico a montar — precisa ter uma entrada em `RECEITAS`.
        hoje: data a gravar no `log_buscas`; `None` usa `date.today()`.

    Returns:
        A `DossieTopico` gravada (`add`/`flush`, sem `commit` — quem chama decide) e o
        `ConteudoDossie` em memória.

    Raises:
        TopicoNaoEncontrado: `topico_slug` não está cadastrado em `topico`.
        KeyError: `topico_slug` não tem receita em `RECEITAS` — `main()` confere isso antes de
            chamar, e reporta "sem receita" em vez de deixar o erro propagar cru.
    """
    topico = _buscar_topico(db, topico_slug)
    receita = RECEITAS[topico_slug]

    cache_html: dict[str, str] = {}
    normas_html: dict[str, str] = {}
    normas_url: dict[str, str] = {}
    for norma_id in {pedido.norma for pedido in receita.pedidos}:
        html = html_offline_da_norma(norma_id, cache_html)
        if html is not None:
            normas_html[norma_id] = html
        normas_url[norma_id] = CATALOGO[norma_id].url

    sumulas_texto, sumulas_url = resolver_sumulas_offline(receita.sumulas)

    conteudo = montar_dossie(
        topico_slug=topico_slug,
        pedidos=receita.pedidos,
        normas_html=normas_html,
        normas_url=normas_url,
        hoje=hoje or date.today(),
        sumulas_pedidas=receita.sumulas,
        sumulas_texto=sumulas_texto,
        sumulas_url=sumulas_url,
    )
    dossie = salvar_dossie(db, topico_id=topico.id, conteudo=conteudo)
    return dossie, conteudo


def construir_dossie_improbidade(
    db: Session, *, hoje: date | None = None
) -> tuple[DossieTopico, ConteudoDossie]:
    """Alias de `construir_dossie(db, SLUG_IMPROBIDADE, hoje=hoje)`.

    Mantido para quem já ligava diretamente na função hardcoded anterior a esta fatia
    (`motor.justificar`, `motor.ligar_por_topico`, seus testes). Chamadores novos devem preferir
    `construir_dossie`.
    """
    return construir_dossie(db, SLUG_IMPROBIDADE, hoje=hoje)


class TopicoComPeso(BaseModel):
    """Um tópico do edital com o peso medido desta fatia (plano §1.2).

    Attributes:
        topico_id: chave de `Topico`.
        slug: `Topico.slug`.
        materia: `Topico.materia`.
        nome: `Topico.nome`.
        questoes_publicaveis: nº de questões publicáveis deste tópico na base — o peso medido.
    """

    topico_id: UUID
    slug: str
    materia: str
    nome: str
    questoes_publicaveis: int


def topicos_de_maior_peso(db: Session, edital_id: UUID, limite: int) -> list[TopicoComPeso]:
    """Os tópicos do edital `edital_id` com mais questões publicáveis na base (peso medido).

    O edital não tem peso declarado por tópico (só peso uniforme por matéria — lacuna registrada
    desde a V2, P-39); nº de questões publicáveis é o único número que a base tem hoje que não é
    estimativa (plano desta fatia, §1.2).

    Args:
        db: sessão de banco.
        edital_id: o edital cujos tópicos entram no ranking (`topico_edital.edital_id`).
        limite: quantos tópicos devolver, no máximo.

    Returns:
        Os tópicos do edital, do maior para o menor nº de questões publicáveis; desempate por
        `slug`. Tópico sem nenhuma questão publicável entra com `questoes_publicaveis=0`.
    """
    contagem = (
        select(Questao.topico_id.label("topico_id"), func.count(Questao.id).label("n"))
        .where(Questao.publicavel.is_(True), Questao.despublicada_em.is_(None))  # P-34
        .group_by(Questao.topico_id)
        .subquery()
    )
    peso = func.coalesce(contagem.c.n, 0)
    consulta = (
        select(Topico, peso)
        .join(TopicoEdital, TopicoEdital.topico_id == Topico.id)
        .outerjoin(contagem, contagem.c.topico_id == Topico.id)
        .where(TopicoEdital.edital_id == edital_id)
        .order_by(peso.desc(), Topico.slug)
        .limit(limite)
    )
    return [
        TopicoComPeso(
            topico_id=topico.id,
            slug=topico.slug,
            materia=topico.materia,
            nome=topico.nome,
            questoes_publicaveis=n,
        )
        for topico, n in db.execute(consulta).all()
    ]


class RelatorioDossie(BaseModel):
    """Uma linha do relatório de `main()`: o que aconteceu ao tentar montar um dossiê.

    Attributes:
        topico_slug: o tópico tentado.
        fontes: nº de fontes resolvidas (`None` quando não havia receita — nada foi tentado).
        lacunas: nº de lacunas declaradas (`None` idem).
        sem_receita: `True` quando `topico_slug` não está em `RECEITAS`.
    """

    topico_slug: str
    fontes: int | None
    lacunas: int | None
    sem_receita: bool


def construir_dossies(
    db: Session, topico_slugs: list[str], *, hoje: date | None = None
) -> list[RelatorioDossie]:
    """Constrói um dossiê por slug de `topico_slugs`, sem propagar `KeyError` cru.

    Pula (com relatório) o que não tem receita cadastrada — quem chama `main()` só vê o texto
    "sem receita cadastrada", nunca um traceback.

    Args:
        db: sessão de banco.
        topico_slugs: os tópicos a tentar, na ordem dada.
        hoje: data a gravar no `log_buscas` de cada dossiê; `None` usa `date.today()`.

    Returns:
        Um `RelatorioDossie` por slug, na mesma ordem.
    """
    relatorios: list[RelatorioDossie] = []
    for slug in topico_slugs:
        if slug not in RECEITAS:
            relatorios.append(
                RelatorioDossie(topico_slug=slug, fontes=None, lacunas=None, sem_receita=True)
            )
            continue
        _dossie, conteudo = construir_dossie(db, slug, hoje=hoje)
        relatorios.append(
            RelatorioDossie(
                topico_slug=slug,
                fontes=len(conteudo.fontes),
                lacunas=len(conteudo.lacunas),
                sem_receita=False,
            )
        )
    return relatorios


def _relatar(relatorios: list[RelatorioDossie]) -> None:
    """Imprime uma linha por tópico tentado, no formato usado pelo diário da fatia."""
    for relatorio in relatorios:
        if relatorio.sem_receita:
            print(f"{relatorio.topico_slug}: sem receita cadastrada — nenhum dossiê montado")
        else:
            print(f"{relatorio.topico_slug}: fontes={relatorio.fontes} lacunas={relatorio.lacunas}")


def _analisar_argumentos(argv: list[str] | None) -> argparse.Namespace:
    """Define e interpreta os argumentos de `main()`."""
    parser = argparse.ArgumentParser(
        description=(
            "Monta e grava o dossiê de um ou mais tópicos (receita cadastrada em `RECEITAS`), "
            "offline e sem LLM — fatia 4 (dossiês dos tópicos de maior peso do edital)."
        )
    )
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--topico", action="append", help="slug de um tópico (repetível)")
    grupo.add_argument(
        "--edital-id", help="constrói os `--top` tópicos de maior peso medido deste edital"
    )
    parser.add_argument(
        "--top", type=int, default=5, help="quantos tópicos do ranking tentar (com --edital-id)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="roda a construção, mas não comita (só imprime o relatório)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, config: Configuracoes | None = None) -> int:
    """Ponto de entrada do comando de construção de dossiê(s).

    Args:
        argv: argumentos da linha de comando; `None` usa `sys.argv` (padrão do `argparse`).
        config: configurações explícitas (testes); `None` lê do ambiente/.env.

    Returns:
        `0` sempre que o comando roda até o fim.
    """
    argumentos = _analisar_argumentos(argv)
    config = config or obter_configuracoes()

    engine = criar_engine(config.database_url)
    fabrica_sessao = criar_fabrica_sessao(engine)
    with fabrica_sessao() as db:
        if argumentos.topico:
            slugs = list(argumentos.topico)
        else:
            ranking = topicos_de_maior_peso(db, UUID(argumentos.edital_id), argumentos.top)
            slugs = [topico.slug for topico in ranking]
        relatorios = construir_dossies(db, slugs)
        if argumentos.dry_run:
            db.rollback()
        else:
            db.commit()
    _relatar(relatorios)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
