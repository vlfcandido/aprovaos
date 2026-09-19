# O que é: testes de `dados/repositorio_aula.py` (fatia 6) — versionamento de `aula` por
# tópico e a leitura da última aula publicada. Quando ler: ao mexer no repositório ou no comando
# `motor/aula.py`.
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Aula, DossieTopico, Topico
from aprovaos.dados.repositorio_aula import (
    aula_publicada_do_topico,
    aula_publicada_do_topico_com_origem,
    proxima_versao,
    salvar_aula,
)
from aprovaos.dados.repositorio_topico_relacao import (
    criar_relacao_equivalente,
    criar_relacao_subconjunto,
)
from aprovaos.dominio.aula import CitacaoAula, ComoABancaCobra, ConteudoAula, RelacionadoAula


def _topico(db: Session, slug: str = "dir-adm-06-improbidade-administrativa") -> Topico:
    topico = Topico(materia="direito-administrativo", nome="Improbidade", slug=slug)
    db.add(topico)
    db.flush()
    return topico


def _dossie(db: Session, topico: Topico) -> DossieTopico:
    dossie = DossieTopico(
        topico_id=topico.id,
        versao=1,
        gerado_em=agora_utc(),
        conteudo="conteúdo do dossiê",
        fontes=[{"id": "F1", "tipo": "norma", "citacao_canonica": "Lei 8.429/1992 art. 1"}],
        bibliografia=[],
        log_buscas=[],
    )
    db.add(dossie)
    db.flush()
    return dossie


def _conteudo() -> ConteudoAula:
    return ConteudoAula(
        texto_denso="A improbidade é punida na forma da lei {{Lei 8.429/1992 art. 1}}.",
        texto_leigo="A lei pune improbidade.",
        citacoes=[
            CitacaoAula(
                canonica="Lei 8.429/1992 art. 1",
                fonte="F1",
                trecho="serão punidos",
                frase_da_aula="A improbidade é punida na forma da lei",
            )
        ],
        relacionados=[
            RelacionadoAula(
                topico_slug="outro-topico", onde="§1", frase="conversa com...", trecho="trecho"
            )
        ],
        como_a_banca_cobra=[ComoABancaCobra(origem="cebraspe 2024 x item 1", o_que_testou="y")],
        lacunas_declaradas=["Lei 8.429/1992 art. 2"],
    )


def test_salvar_aula_grava_versao_1_publicada(db: Session) -> None:
    topico = _topico(db)
    dossie = _dossie(db, topico)

    aula = salvar_aula(db, topico_id=topico.id, dossie=dossie, conteudo=_conteudo())
    db.flush()

    assert aula.topico_id == topico.id
    assert aula.dossie_id == dossie.id
    assert aula.dossie_versao == dossie.versao
    assert aula.versao == 1
    assert aula.publicada is True
    assert aula.validado_em is not None
    assert aula.citacoes[0]["canonica"] == "Lei 8.429/1992 art. 1"
    assert aula.relacionados[0]["topico_slug"] == "outro-topico"
    assert aula.como_a_banca_cobra[0]["origem"] == "cebraspe 2024 x item 1"
    assert aula.lacunas_declaradas == ["Lei 8.429/1992 art. 2"]
    assert aula.mnemonico is None
    assert aula.audio_url is None


def test_salvar_aula_de_novo_cria_versao_2(db: Session) -> None:
    topico = _topico(db)
    dossie = _dossie(db, topico)
    salvar_aula(db, topico_id=topico.id, dossie=dossie, conteudo=_conteudo())
    db.flush()

    segunda = salvar_aula(db, topico_id=topico.id, dossie=dossie, conteudo=_conteudo())
    db.flush()

    assert segunda.versao == 2
    assert db.query(Aula).filter_by(topico_id=topico.id).count() == 2


def test_proxima_versao_e_1_sem_aula(db: Session) -> None:
    topico = _topico(db)
    assert proxima_versao(db, topico.id) == 1


def test_aula_publicada_do_topico_devolve_a_ultima_versao(db: Session) -> None:
    topico = _topico(db)
    dossie = _dossie(db, topico)
    salvar_aula(db, topico_id=topico.id, dossie=dossie, conteudo=_conteudo())
    segunda = salvar_aula(db, topico_id=topico.id, dossie=dossie, conteudo=_conteudo())
    db.flush()

    encontrada = aula_publicada_do_topico(db, topico.id)
    assert encontrada is not None
    assert encontrada.id == segunda.id


def test_aula_publicada_do_topico_sem_aula_devolve_none(db: Session) -> None:
    topico = _topico(db)
    assert aula_publicada_do_topico(db, topico.id) is None


def test_aula_publicada_do_topico_segue_relacao_de_equivalencia(db: Session) -> None:
    """Fecha a P-52 (ADR-0041): um tópico sem aula própria, mas equivalente a outro que tem,

    encontra a aula do equivalente."""
    ficticio = _topico(db, "dir-adm-06-improbidade-administrativa")
    real = _topico(db, "noc-dir-adm-06-6-improbidade")
    dossie = _dossie(db, ficticio)
    aula = salvar_aula(db, topico_id=ficticio.id, dossie=dossie, conteudo=_conteudo())
    criar_relacao_equivalente(
        db, de_id=ficticio.id, para_id=real.id, evidencia="ambos citam a Lei nº 8.429/1992"
    )
    db.flush()

    encontrada = aula_publicada_do_topico(db, real.id)
    assert encontrada is not None
    assert encontrada.id == aula.id


def test_aula_publicada_do_topico_prefere_a_propria_a_equivalente(db: Session) -> None:
    ficticio = _topico(db, "dir-adm-06-improbidade-administrativa")
    real = _topico(db, "noc-dir-adm-06-6-improbidade")
    dossie_ficticio = _dossie(db, ficticio)
    dossie_real = _dossie(db, real)
    salvar_aula(db, topico_id=ficticio.id, dossie=dossie_ficticio, conteudo=_conteudo())
    aula_propria = salvar_aula(db, topico_id=real.id, dossie=dossie_real, conteudo=_conteudo())
    criar_relacao_equivalente(db, de_id=ficticio.id, para_id=real.id, evidencia="mesma lei")
    db.flush()

    encontrada = aula_publicada_do_topico(db, real.id)
    assert encontrada is not None
    assert encontrada.id == aula_propria.id


# --- aula_publicada_do_topico_com_origem (I1: cobertura parcial avisada) -----------------------


def test_com_origem_devolve_direta_quando_a_propria_tem_aula(db: Session) -> None:
    topico = _topico(db)
    dossie = _dossie(db, topico)
    aula = salvar_aula(db, topico_id=topico.id, dossie=dossie, conteudo=_conteudo())

    resultado = aula_publicada_do_topico_com_origem(db, topico.id)

    assert resultado is not None
    encontrada, origem = resultado
    assert encontrada.id == aula.id
    assert origem == "direta"


def test_com_origem_devolve_equivalencia_curada_para_par_pleno(db: Session) -> None:
    ficticio = _topico(db, "dir-adm-06-improbidade-administrativa")
    real = _topico(db, "noc-dir-adm-06-6-improbidade")
    dossie = _dossie(db, ficticio)
    aula = salvar_aula(db, topico_id=ficticio.id, dossie=dossie, conteudo=_conteudo())
    criar_relacao_equivalente(db, de_id=ficticio.id, para_id=real.id, evidencia="mesma lei")
    db.flush()

    resultado = aula_publicada_do_topico_com_origem(db, real.id)

    assert resultado is not None
    encontrada, origem = resultado
    assert encontrada.id == aula.id
    assert origem == "equivalencia_curada"


def test_com_origem_devolve_subconjunto_curado_para_par_parcial(db: Session) -> None:
    """A aluna que abre `noc-dir-pro-civ-07-recursos` ("Dos recursos") encontra a aula do
    dossiê parcial de Cascavel — mas a origem devolvida avisa que é cobertura parcial (I1),
    diferente do caso pleno acima."""
    cascavel = _topico(db, "dir-pro-civ-05-recursos-apelacao")
    tjpr = _topico(db, "noc-dir-pro-civ-07-recursos")
    dossie = _dossie(db, cascavel)
    aula = salvar_aula(db, topico_id=cascavel.id, dossie=dossie, conteudo=_conteudo())
    criar_relacao_subconjunto(
        db, de_id=cascavel.id, para_id=tjpr.id, evidencia="cobre só parte do item"
    )
    db.flush()

    resultado = aula_publicada_do_topico_com_origem(db, tjpr.id)

    assert resultado is not None
    encontrada, origem = resultado
    assert encontrada.id == aula.id
    assert origem == "subconjunto_curado"


def test_com_origem_prefere_equivalencia_plena_a_subconjunto(db: Session) -> None:
    """Se um tópico tem os dois tipos de relação (não deveria, mas a leitura tem de ser
    determinística), a equivalência plena vence — é a informação mais forte."""
    plena = _topico(db, "a-plena")
    parcial = _topico(db, "b-parcial")
    alvo = _topico(db, "c-alvo")
    dossie_plena = _dossie(db, plena)
    dossie_parcial = _dossie(db, parcial)
    aula_plena = salvar_aula(db, topico_id=plena.id, dossie=dossie_plena, conteudo=_conteudo())
    salvar_aula(db, topico_id=parcial.id, dossie=dossie_parcial, conteudo=_conteudo())
    criar_relacao_equivalente(db, de_id=alvo.id, para_id=plena.id, evidencia="mesma lei")
    criar_relacao_subconjunto(db, de_id=alvo.id, para_id=parcial.id, evidencia="parte do item")
    db.flush()

    resultado = aula_publicada_do_topico_com_origem(db, alvo.id)

    assert resultado is not None
    encontrada, origem = resultado
    assert encontrada.id == aula_plena.id
    assert origem == "equivalencia_curada"


def test_com_origem_sem_aula_nenhuma_devolve_none(db: Session) -> None:
    topico = _topico(db)
    assert aula_publicada_do_topico_com_origem(db, topico.id) is None
