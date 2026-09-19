# O que é: testes do comando `motor/relacionar_topicos.py` (ADR-0041, fecha a P-52; I1) — liga os
# pares plenos curados em `RELACOES` e os parciais em `RELACOES_PARCIAIS`. Quando ler: ao
# acrescentar um par novo, ou ao investigar por que um par não foi ligado no `dev.db`.
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Topico, TopicoRelacao
from aprovaos.dados.repositorio_topico_relacao import (
    ORIGEM_EQUIVALENCIA_CURADA,
    ORIGEM_SUBCONJUNTO_CURADO,
    criar_relacao_subconjunto,
    topicos_subconjunto,
)
from aprovaos.motor.relacionar_topicos import RELACOES, RELACOES_PARCIAIS, relacionar_topicos


def _topico(db: Session, slug: str) -> Topico:
    topico = Topico(materia="direito-administrativo", nome=slug, slug=slug)
    db.add(topico)
    db.flush()
    return topico


def test_relacionar_topicos_liga_par_existente(db: Session) -> None:
    slug_a, slug_b = next(iter(RELACOES))
    _topico(db, slug_a)
    _topico(db, slug_b)
    db.flush()

    relatorio = relacionar_topicos(db)

    linha = next(item for item in relatorio if item.pares == (slug_a, slug_b))
    assert linha.status == "criada"
    assert db.query(TopicoRelacao).filter_by(origem=ORIGEM_EQUIVALENCIA_CURADA).count() >= 1


def test_relacionar_topicos_e_idempotente(db: Session) -> None:
    for slug_a, slug_b in RELACOES:
        _topico(db, slug_a)
        _topico(db, slug_b)
    db.flush()

    relacionar_topicos(db)
    db.flush()
    total_depois_da_primeira = db.query(TopicoRelacao).count()

    segunda = relacionar_topicos(db)
    db.flush()

    assert all(item.status in {"ja_existia"} for item in segunda)
    assert db.query(TopicoRelacao).count() == total_depois_da_primeira


def test_relacionar_topicos_reporta_slug_sem_topico_sem_derrubar(db: Session) -> None:
    relatorio = relacionar_topicos(db, pares={("materia-99-a", "materia-99-b"): "evidência x"})

    assert len(relatorio) == 1
    assert relatorio[0].status == "sem_topico"
    assert db.query(TopicoRelacao).count() == 0


def test_todos_os_pares_de_relacoes_tem_slugs_diferentes() -> None:
    """Nenhum par de `RELACOES` liga um tópico a ele mesmo — erro de copiar e colar."""
    for slug_a, slug_b in RELACOES:
        assert slug_a != slug_b


# --- RELACOES_PARCIAIS (I1: cobertura parcial não é equivalência plena) -----------------------


def test_par_de_recursos_esta_em_parciais_nao_em_plenas() -> None:
    """O par de "recursos" (Cascavel × TJ-PR) tem evidência de cobertura parcial — não pode
    estar em `RELACOES` (equivalência plena)."""
    par_recursos = ("dir-pro-civ-05-recursos-apelacao", "noc-dir-pro-civ-07-recursos")
    assert par_recursos in RELACOES_PARCIAIS
    assert par_recursos not in RELACOES


def test_relacionar_topicos_liga_par_parcial_com_peso_menor_que_1(db: Session) -> None:
    slug_a, slug_b = next(iter(RELACOES_PARCIAIS))
    _topico(db, slug_a)
    _topico(db, slug_b)
    db.flush()

    relatorio = relacionar_topicos(
        db,
        RELACOES_PARCIAIS,
        criar_relacao=criar_relacao_subconjunto,
        ja_ligados=topicos_subconjunto,
    )

    linha = next(item for item in relatorio if item.pares == (slug_a, slug_b))
    assert linha.status == "criada"
    relacao = db.query(TopicoRelacao).filter_by(origem=ORIGEM_SUBCONJUNTO_CURADO).one()
    assert float(relacao.peso) < 1.0


def test_todos_os_pares_de_relacoes_parciais_tem_slugs_diferentes() -> None:
    for slug_a, slug_b in RELACOES_PARCIAIS:
        assert slug_a != slug_b
