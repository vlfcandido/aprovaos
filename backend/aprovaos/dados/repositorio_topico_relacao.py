"""Repositório de `topico_relacao`: a ponte entre tópicos de editais diferentes.

O que é: duas origens curadas, cada uma com sua força (`peso`) e sua função de leitura —
`criar_relacao_equivalente`/`topicos_equivalentes` para equivalência **plena**
(`origem="equivalencia_curada"`, peso 1 — o mesmo assunto, visto por dois editais) e
`criar_relacao_subconjunto`/`topicos_subconjunto` para cobertura **parcial**
(`origem="subconjunto_curado"`, peso < 1 — um dossiê/aula cobre só um subconjunto do item do
outro edital, nunca o item inteiro). As duas são idempotentes nas duas direções (nunca duplicam
o mesmo par, gravado em qualquer ordem) e simétricas na leitura, mesmo sendo arestas
direcionadas no banco.

Correção de 19/09/2026 (revisão independente, I1): a P-52/ADR-0041 original gravava **todo** par
curado como `equivalencia_curada` (peso pleno), inclusive um par cuja própria evidência dizia "a
cobertura do dossiê é parcial" — a aluna recebia uma aula de "apelação, agravo e embargos"
rotulada como a aula inteira de "Dos recursos" do TJ-PR, sem aviso nenhum. Esta separação
existe para que a tela (que hoje só consegue avisar isso na trilha, não na página de aula —
`web/templates/aula/ver.html` acabou de ser corrigida e está fora do escopo desta correção) saiba
distinguir "é a mesma coisa" de "cobre só uma parte", em vez de tratar as duas como equivalentes.

É o que fecha a P-52 (ADR-0041, `docs/DECISOES.md`): dossiê e aula ficam pendurados no
`topico_id` de um único edital; quem lê por tópico (`repositorio_dossie
.dossie_mais_recente_do_topico`, `repositorio_aula.aula_publicada_do_topico`,
`motor.ligar_por_topico`) passa a tentar também os tópicos ligados antes de desistir —
equivalência plena primeiro, subconjunto depois (`repositorio_aula
.aula_publicada_do_topico_com_origem` é quem sabe de qual dos dois veio, para a trilha avisar).

Quando ler: ao ligar um novo par de tópicos, plena ou parcial (`motor/relacionar_topicos.py`), ou
ao investigar por que um tópico não encontrou o dossiê/aula/citação que devia, ou encontrou sem
avisar que é cobertura parcial.
"""

from typing import Final, Literal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import TopicoRelacao

OrigemTopicoRelacao = Literal["equivalencia_curada", "subconjunto_curado"]

#: Os dois valores de `origem` que este repositório produz nesta rodada — os dois que
#: `docs/04-modelo-de-dados.md` §3 já previa (`edital`/`dossie`) e `coocorrencia` ainda não têm
#: produtor (ADR-0041/I1). Tipadas como `OrigemTopicoRelacao` (não `str` solto) para o mypy
#: estreitar cada chamada de `_criar_relacao`/`_topicos_por_origem` sozinho.
ORIGEM_EQUIVALENCIA_CURADA: Final[OrigemTopicoRelacao] = "equivalencia_curada"
ORIGEM_SUBCONJUNTO_CURADO: Final[OrigemTopicoRelacao] = "subconjunto_curado"

#: `peso` de toda relação de equivalência curada — é uma correspondência plena (o mesmo assunto
#: visto por dois editais), nunca parcial.
PESO_EQUIVALENCIA_CURADA = 1

#: `peso` de toda relação de subconjunto curado — sinal direcional de cobertura parcial (não é
#: uma fração medida do item; medir "quanto" um dossiê cobre exigiria decompor o item do outro
#: edital em partes comparáveis, fora do escopo desta correção), sempre `< PESO_EQUIVALENCIA
#: _CURADA` para nunca ser confundido com equivalência plena em nenhuma soma/ranking futuro.
PESO_SUBCONJUNTO_CURADO = 0.5


def _relacao_existente(
    db: Session, de_id: UUID, para_id: UUID, origem: OrigemTopicoRelacao
) -> TopicoRelacao | None:
    """Acha a relação de `origem` já gravada para o par, em qualquer direção."""
    return db.scalars(
        select(TopicoRelacao).where(
            TopicoRelacao.origem == origem,
            or_(
                (TopicoRelacao.de_id == de_id) & (TopicoRelacao.para_id == para_id),
                (TopicoRelacao.de_id == para_id) & (TopicoRelacao.para_id == de_id),
            ),
        )
    ).first()


def _criar_relacao(
    db: Session,
    *,
    de_id: UUID,
    para_id: UUID,
    evidencia: str,
    origem: OrigemTopicoRelacao,
    peso: float,
) -> TopicoRelacao:
    """Grava (ou devolve a já existente) a relação de `origem` entre `de_id` e `para_id`.

    Núcleo comum de `criar_relacao_equivalente`/`criar_relacao_subconjunto` — só elas são
    públicas, para que quem chama nunca escolha `peso` na mão (a força de cada origem é fixa).
    """
    if de_id == para_id:
        raise ValueError("não é possível relacionar um tópico com o mesmo tópico")

    existente = _relacao_existente(db, de_id, para_id, origem)
    if existente is not None:
        return existente

    relacao = TopicoRelacao(
        de_id=de_id, para_id=para_id, peso=peso, origem=origem, evidencia=evidencia
    )
    db.add(relacao)
    db.flush()
    return relacao


def criar_relacao_equivalente(
    db: Session, *, de_id: UUID, para_id: UUID, evidencia: str
) -> TopicoRelacao:
    """Grava (ou devolve a já existente) a equivalência **plena** entre `de_id` e `para_id`.

    Args:
        db: sessão de banco.
        de_id: um lado da equivalência.
        para_id: o outro lado — a ordem não importa (a relação é simétrica na leitura).
        evidencia: o porquê rastreável da equivalência (ex.: "ambos citam a Lei nº 8.429/1992"),
            nunca "parecem iguais" (ADR-0041/ADR-0036 — na dúvida, não relacione) e nunca uma
            evidência que já diz "cobertura parcial" (isso é `criar_relacao_subconjunto`, I1).

    Returns:
        A `TopicoRelacao` gravada nesta chamada, ou a que já existia para o par (idempotente nas
        duas direções — nunca cria uma segunda linha para o mesmo par).

    Raises:
        ValueError: se `de_id == para_id` (um tópico não é equivalente a si mesmo).
    """
    return _criar_relacao(
        db,
        de_id=de_id,
        para_id=para_id,
        evidencia=evidencia,
        origem=ORIGEM_EQUIVALENCIA_CURADA,
        peso=PESO_EQUIVALENCIA_CURADA,
    )


def criar_relacao_subconjunto(
    db: Session, *, de_id: UUID, para_id: UUID, evidencia: str
) -> TopicoRelacao:
    """Grava (ou devolve a já existente) a cobertura **parcial** entre `de_id` e `para_id` (I1).

    Use quando a evidência da curadoria já diz que um lado cobre só um subconjunto do outro
    (ex.: um dossiê que detalha apelação/agravo/embargos para um item genérico "Dos recursos")
    — nunca como equivalência plena, mesmo que os dois falem do "mesmo assunto" em algum grau.

    Args:
        db: sessão de banco.
        de_id: um lado da relação.
        para_id: o outro lado — a ordem não importa (a relação é simétrica na leitura).
        evidencia: o porquê rastreável, incluindo o que fica de fora (ex.: "cobre apelação,
            agravo de instrumento e embargos de declaração; não cobre os demais recursos do
            item").

    Returns:
        A `TopicoRelacao` gravada nesta chamada, ou a que já existia para o par (idempotente nas
        duas direções).

    Raises:
        ValueError: se `de_id == para_id`.
    """
    return _criar_relacao(
        db,
        de_id=de_id,
        para_id=para_id,
        evidencia=evidencia,
        origem=ORIGEM_SUBCONJUNTO_CURADO,
        peso=PESO_SUBCONJUNTO_CURADO,
    )


def _topicos_por_origem(db: Session, topico_id: UUID, origem: OrigemTopicoRelacao) -> list[UUID]:
    """Os `topico_id` ligados a `topico_id` por `origem`, nas duas direções, em ordem de criação."""
    linhas = db.scalars(
        select(TopicoRelacao)
        .where(
            TopicoRelacao.origem == origem,
            or_(TopicoRelacao.de_id == topico_id, TopicoRelacao.para_id == topico_id),
        )
        .order_by(TopicoRelacao.criado_em.asc())
    ).all()
    return [linha.para_id if linha.de_id == topico_id else linha.de_id for linha in linhas]


def topicos_equivalentes(db: Session, topico_id: UUID) -> list[UUID]:
    """Os `topico_id` ligados a `topico_id` por equivalência **plena**, nas duas direções.

    Nunca inclui relação `subconjunto_curado` (I1) — quem precisa das duas (leitura de
    dossiê/aula para a tela) chama `topicos_subconjunto` também, explicitamente.

    Args:
        db: sessão de banco.
        topico_id: o tópico cujos equivalentes se quer.

    Returns:
        Lista de `topico_id` (pode ser vazia); ordem pela criação da relação (`criado_em`), para
        ser determinística quando houver mais de um equivalente.
    """
    return _topicos_por_origem(db, topico_id, ORIGEM_EQUIVALENCIA_CURADA)


def topicos_subconjunto(db: Session, topico_id: UUID) -> list[UUID]:
    """Os `topico_id` ligados a `topico_id` por cobertura **parcial** (I1), nas duas direções.

    Args:
        db: sessão de banco.
        topico_id: o tópico cujos "subconjuntos" curados se quer.

    Returns:
        Lista de `topico_id` (pode ser vazia); mesma ordem de `topicos_equivalentes`.
    """
    return _topicos_por_origem(db, topico_id, ORIGEM_SUBCONJUNTO_CURADO)
