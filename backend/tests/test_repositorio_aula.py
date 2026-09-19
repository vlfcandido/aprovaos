# O que é: testes de `dados/repositorio_aula.py` (fatia 6) — versionamento de `aula` por
# tópico e a leitura da última aula publicada. Quando ler: ao mexer no repositório ou no comando
# `motor/aula.py`.
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Aula, DossieTopico, Topico
from aprovaos.dados.repositorio_aula import aula_publicada_do_topico, proxima_versao, salvar_aula
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
