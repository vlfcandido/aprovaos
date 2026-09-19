"""Repositório de `topico_relacao`: a ponte entre tópicos equivalentes de editais diferentes.

O que é: `criar_relacao_equivalente` grava uma aresta `origem="equivalencia_curada"` (idempotente
nas duas direções — nunca duplica o mesmo par, gravado em qualquer ordem); `topicos_equivalentes`
devolve os `topico_id` ligados a um tópico por essa origem, nas duas direções (a relação é
simétrica na leitura mesmo sendo uma aresta direcionada no banco). É o que fecha a P-52 (ADR-0041,
`docs/DECISOES.md`): dossiê e aula ficam pendurados no `topico_id` de um único edital; quem lê por
tópico (`repositorio_dossie.dossie_mais_recente_do_topico`, `repositorio_aula
.aula_publicada_do_topico`, `motor.ligar_por_topico`) passa a tentar também os equivalentes antes
de desistir.

Quando ler: ao ligar um novo par de tópicos equivalentes (`motor/relacionar_topicos.py`), ou ao
investigar por que um tópico não encontrou o dossiê/aula/citação que devia.
"""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import TopicoRelacao

#: Único valor de `origem` que este repositório produz nesta rodada — os outros três que
#: `docs/04-modelo-de-dados.md` §3 já previa (`edital`/`dossie`/`coocorrencia`) ainda não têm
#: produtor (ADR-0041).
ORIGEM_EQUIVALENCIA_CURADA = "equivalencia_curada"

#: `peso` de toda relação de equivalência curada — é uma correspondência plena (o mesmo assunto
#: visto por dois editais), nunca parcial.
PESO_EQUIVALENCIA_CURADA = 1


def _relacao_existente(db: Session, de_id: UUID, para_id: UUID) -> TopicoRelacao | None:
    """Acha a relação de equivalência já gravada para o par, em qualquer direção."""
    return db.scalars(
        select(TopicoRelacao).where(
            TopicoRelacao.origem == ORIGEM_EQUIVALENCIA_CURADA,
            or_(
                (TopicoRelacao.de_id == de_id) & (TopicoRelacao.para_id == para_id),
                (TopicoRelacao.de_id == para_id) & (TopicoRelacao.para_id == de_id),
            ),
        )
    ).first()


def criar_relacao_equivalente(
    db: Session, *, de_id: UUID, para_id: UUID, evidencia: str
) -> TopicoRelacao:
    """Grava (ou devolve a já existente) a equivalência curada entre `de_id` e `para_id`.

    Args:
        db: sessão de banco.
        de_id: um lado da equivalência.
        para_id: o outro lado — a ordem não importa (a relação é simétrica na leitura).
        evidencia: o porquê rastreável da equivalência (ex.: "ambos citam a Lei nº 8.429/1992"),
            nunca "parecem iguais" (ADR-0041/ADR-0036 — na dúvida, não relacione).

    Returns:
        A `TopicoRelacao` gravada nesta chamada, ou a que já existia para o par (idempotente nas
        duas direções — nunca cria uma segunda linha para o mesmo par).

    Raises:
        ValueError: se `de_id == para_id` (um tópico não é equivalente a si mesmo).
    """
    if de_id == para_id:
        raise ValueError("não é possível relacionar um tópico com o mesmo tópico")

    existente = _relacao_existente(db, de_id, para_id)
    if existente is not None:
        return existente

    relacao = TopicoRelacao(
        de_id=de_id,
        para_id=para_id,
        peso=PESO_EQUIVALENCIA_CURADA,
        origem=ORIGEM_EQUIVALENCIA_CURADA,
        evidencia=evidencia,
    )
    db.add(relacao)
    db.flush()
    return relacao


def topicos_equivalentes(db: Session, topico_id: UUID) -> list[UUID]:
    """Os `topico_id` ligados a `topico_id` por equivalência curada, nas duas direções.

    Args:
        db: sessão de banco.
        topico_id: o tópico cujos equivalentes se quer.

    Returns:
        Lista de `topico_id` (pode ser vazia); ordem pela criação da relação (`criado_em`), para
        ser determinística quando houver mais de um equivalente.
    """
    linhas = db.scalars(
        select(TopicoRelacao)
        .where(
            TopicoRelacao.origem == ORIGEM_EQUIVALENCIA_CURADA,
            or_(TopicoRelacao.de_id == topico_id, TopicoRelacao.para_id == topico_id),
        )
        .order_by(TopicoRelacao.criado_em.asc())
    ).all()
    return [linha.para_id if linha.de_id == topico_id else linha.de_id for linha in linhas]
