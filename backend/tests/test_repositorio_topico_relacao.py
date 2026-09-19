# O que é: testes de `dados/repositorio_topico_relacao.py` (ADR-0041) — a ponte entre tópicos
# equivalentes de editais diferentes (`topico_relacao`, origem `equivalencia_curada`).
# Quando ler: ao mexer no repositório, no comando `motor/relacionar_topicos.py`, ou em qualquer
# leitura de dossiê/aula/questão que precise atravessar a relação.
import pytest
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Topico, TopicoRelacao
from aprovaos.dados.repositorio_topico_relacao import (
    ORIGEM_EQUIVALENCIA_CURADA,
    criar_relacao_equivalente,
    topicos_equivalentes,
)


def _topico(db: Session, slug: str) -> Topico:
    topico = Topico(materia="direito-administrativo", nome=slug, slug=slug)
    db.add(topico)
    db.flush()
    return topico


def test_criar_relacao_equivalente_grava_peso_1_e_evidencia(db: Session) -> None:
    a = _topico(db, "dir-adm-06-improbidade-administrativa")
    b = _topico(db, "noc-dir-adm-06-6-improbidade")

    relacao = criar_relacao_equivalente(
        db, de_id=a.id, para_id=b.id, evidencia="ambos citam a Lei nº 8.429/1992"
    )
    db.flush()

    assert relacao.de_id == a.id
    assert relacao.para_id == b.id
    assert relacao.origem == ORIGEM_EQUIVALENCIA_CURADA
    assert float(relacao.peso) == 1.0
    assert relacao.evidencia == "ambos citam a Lei nº 8.429/1992"
    assert db.query(TopicoRelacao).count() == 1


def test_criar_relacao_equivalente_e_idempotente_nas_duas_direcoes(db: Session) -> None:
    a = _topico(db, "dir-adm-06-improbidade-administrativa")
    b = _topico(db, "noc-dir-adm-06-6-improbidade")
    criar_relacao_equivalente(db, de_id=a.id, para_id=b.id, evidencia="mesma lei")
    db.flush()

    # de novo, na mesma direção
    criar_relacao_equivalente(db, de_id=a.id, para_id=b.id, evidencia="mesma lei")
    db.flush()
    assert db.query(TopicoRelacao).count() == 1

    # e na direção invertida — é a mesma equivalência, não uma segunda
    criar_relacao_equivalente(db, de_id=b.id, para_id=a.id, evidencia="mesma lei")
    db.flush()
    assert db.query(TopicoRelacao).count() == 1


def test_criar_relacao_equivalente_recusa_topico_consigo_mesmo(db: Session) -> None:
    a = _topico(db, "dir-adm-06-improbidade-administrativa")

    with pytest.raises(ValueError, match="mesmo tópico"):
        criar_relacao_equivalente(db, de_id=a.id, para_id=a.id, evidencia="x")


def test_topicos_equivalentes_encontra_nas_duas_direcoes(db: Session) -> None:
    a = _topico(db, "dir-adm-06-improbidade-administrativa")
    b = _topico(db, "noc-dir-adm-06-6-improbidade")
    criar_relacao_equivalente(db, de_id=a.id, para_id=b.id, evidencia="mesma lei")
    db.flush()

    assert topicos_equivalentes(db, a.id) == [b.id]
    assert topicos_equivalentes(db, b.id) == [a.id]


def test_topicos_equivalentes_sem_relacao_devolve_lista_vazia(db: Session) -> None:
    a = _topico(db, "dir-adm-06-improbidade-administrativa")
    assert topicos_equivalentes(db, a.id) == []
