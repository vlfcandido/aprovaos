# O que é: testes do passo 2 da fundação jurídica — `dados.repositorio_citacao`: dedup de
# `dispositivo_legal` por `citacao_canonica` e de `citacao` por (conteúdo, dispositivo).
# Quando ler: ao mexer em `dados/repositorio_citacao.py` ou no comando `motor/ancorar.py`.
from uuid import uuid4

from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Citacao, DispositivoLegal
from aprovaos.dados.repositorio_citacao import (
    buscar_dispositivo_por_citacao_canonica,
    buscar_ou_criar_dispositivo,
    dispositivos_da_questao,
    maior_posicao,
    registrar_citacao,
)


def test_buscar_ou_criar_dispositivo_cria_na_primeira_chamada(db: Session) -> None:
    """A primeira chamada para uma `citacao_canonica` nova grava a linha com todos os campos."""
    dispositivo = buscar_ou_criar_dispositivo(
        db,
        citacao_canonica="CF/88 art. 37",
        norma="cf-1988",
        artigo="37",
        inciso=None,
        paragrafo=None,
        texto="Art. 37. A administração pública...",
        vigente=True,
        fonte_url="https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
    )
    db.flush()

    assert dispositivo.id is not None
    assert dispositivo.norma == "cf-1988"
    assert dispositivo.artigo == "37"
    assert db.query(DispositivoLegal).count() == 1


def test_buscar_ou_criar_dispositivo_e_idempotente_por_citacao_canonica(db: Session) -> None:
    """Duas chamadas com a mesma `citacao_canonica` devolvem a mesma linha — nunca duplicam."""
    primeiro = buscar_ou_criar_dispositivo(
        db,
        citacao_canonica="CF/88 art. 37",
        norma="cf-1988",
        artigo="37",
        inciso=None,
        paragrafo=None,
        texto="Art. 37. A administração pública...",
        vigente=True,
        fonte_url="https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
    )
    segundo = buscar_ou_criar_dispositivo(
        db,
        citacao_canonica="CF/88 art. 37",
        norma="cf-1988",
        artigo="37",
        inciso=None,
        paragrafo=None,
        texto="Art. 37. A administração pública...",
        vigente=True,
        fonte_url="https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
    )
    db.flush()

    assert primeiro.id == segundo.id
    assert db.query(DispositivoLegal).count() == 1


def test_registrar_citacao_grava_uma_linha_por_questao(db: Session) -> None:
    """Uma citação nova (conteúdo + dispositivo ainda não ligados) grava a linha."""
    dispositivo = buscar_ou_criar_dispositivo(
        db,
        citacao_canonica="CF/88 art. 37",
        norma="cf-1988",
        artigo="37",
        inciso=None,
        paragrafo=None,
        texto="Art. 37. A administração pública...",
        vigente=True,
        fonte_url="https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
    )
    db.flush()
    questao_id = uuid4()

    citacao = registrar_citacao(
        db,
        conteudo_tipo="questao",
        conteudo_id=questao_id,
        dispositivo_id=dispositivo.id,
        posicao=1,
    )
    db.flush()

    assert citacao is not None
    assert db.query(Citacao).count() == 1


def test_registrar_citacao_e_idempotente_por_conteudo_e_dispositivo(db: Session) -> None:
    """Rodar o comando duas vezes sobre a mesma questão não duplica a linha em `citacao`."""
    dispositivo = buscar_ou_criar_dispositivo(
        db,
        citacao_canonica="CF/88 art. 37",
        norma="cf-1988",
        artigo="37",
        inciso=None,
        paragrafo=None,
        texto="Art. 37. A administração pública...",
        vigente=True,
        fonte_url="https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
    )
    db.flush()
    questao_id = uuid4()

    primeira = registrar_citacao(
        db,
        conteudo_tipo="questao",
        conteudo_id=questao_id,
        dispositivo_id=dispositivo.id,
        posicao=1,
    )
    segunda = registrar_citacao(
        db,
        conteudo_tipo="questao",
        conteudo_id=questao_id,
        dispositivo_id=dispositivo.id,
        posicao=1,
    )
    db.flush()

    assert primeira is not None
    assert segunda is None
    assert db.query(Citacao).count() == 1


def test_dez_questoes_citando_o_mesmo_artigo_e_um_dispositivo_e_dez_citacoes(db: Session) -> None:
    """O mesmo artigo citado por dez questões é uma linha em `dispositivo_legal`, dez em
    `citacao`."""
    for _ in range(10):
        dispositivo = buscar_ou_criar_dispositivo(
            db,
            citacao_canonica="CF/88 art. 37",
            norma="cf-1988",
            artigo="37",
            inciso=None,
            paragrafo=None,
            texto="Art. 37. A administração pública...",
            vigente=True,
            fonte_url="https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
        )
        db.flush()
        registrar_citacao(
            db,
            conteudo_tipo="questao",
            conteudo_id=uuid4(),
            dispositivo_id=dispositivo.id,
            posicao=1,
        )
        db.flush()

    assert db.query(DispositivoLegal).count() == 1
    assert db.query(Citacao).count() == 10


def test_buscar_dispositivo_por_citacao_canonica_acha_o_existente(db: Session) -> None:
    """Usado por `motor.ligar_por_topico` — o dossiê já criou o dispositivo; aqui só se busca."""
    buscar_ou_criar_dispositivo(
        db,
        citacao_canonica="Lei 8.429/1992 art. 1 § 2º",
        norma="lei-8429-1992",
        artigo="1",
        inciso=None,
        paragrafo="2",
        texto="§ 2º Considera-se dolo [...]",
        vigente=True,
        fonte_url="https://www.planalto.gov.br/ccivil_03/leis/l8429.htm",
    )
    db.flush()

    encontrado = buscar_dispositivo_por_citacao_canonica(db, "Lei 8.429/1992 art. 1 § 2º")

    assert encontrado is not None
    assert encontrado.paragrafo == "2"


def test_buscar_dispositivo_por_citacao_canonica_devolve_none_se_nao_existe(db: Session) -> None:
    assert buscar_dispositivo_por_citacao_canonica(db, "Lei 8.429/1992 art. 999") is None


def test_maior_posicao_e_zero_sem_nenhuma_citacao(db: Session) -> None:
    assert maior_posicao(db, conteudo_tipo="questao", conteudo_id=uuid4()) == 0


def test_maior_posicao_acompanha_citacoes_existentes(db: Session) -> None:
    dispositivo = buscar_ou_criar_dispositivo(
        db,
        citacao_canonica="CF/88 art. 37",
        norma="cf-1988",
        artigo="37",
        inciso=None,
        paragrafo=None,
        texto="Art. 37. A administração pública...",
        vigente=True,
        fonte_url="https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
    )
    db.flush()
    questao_id = uuid4()
    registrar_citacao(
        db,
        conteudo_tipo="questao",
        conteudo_id=questao_id,
        dispositivo_id=dispositivo.id,
        posicao=3,
    )
    db.flush()

    assert maior_posicao(db, conteudo_tipo="questao", conteudo_id=questao_id) == 3
    assert maior_posicao(db, conteudo_tipo="questao", conteudo_id=uuid4()) == 0


def test_dispositivos_da_questao_na_ordem_da_posicao(db: Session) -> None:
    """`dispositivos_da_questao` devolve só os dispositivos ligados a esta questão, por posição."""
    art1 = buscar_ou_criar_dispositivo(
        db,
        citacao_canonica="Lei 8.429/1992 art. 1",
        norma="lei-8429-1992",
        artigo="1",
        inciso=None,
        paragrafo=None,
        texto="Art. 1º Os atos de improbidade [...]",
        vigente=True,
        fonte_url="https://www.planalto.gov.br/ccivil_03/leis/l8429.htm",
    )
    art2 = buscar_ou_criar_dispositivo(
        db,
        citacao_canonica="Lei 8.429/1992 art. 2",
        norma="lei-8429-1992",
        artigo="2",
        inciso=None,
        paragrafo=None,
        texto="Art. 2º Reputa-se agente público [...]",
        vigente=True,
        fonte_url="https://www.planalto.gov.br/ccivil_03/leis/l8429.htm",
    )
    db.flush()
    questao_id = uuid4()
    outra_questao_id = uuid4()
    registrar_citacao(
        db, conteudo_tipo="questao", conteudo_id=questao_id, dispositivo_id=art2.id, posicao=1
    )
    registrar_citacao(
        db, conteudo_tipo="questao", conteudo_id=questao_id, dispositivo_id=art1.id, posicao=2
    )
    registrar_citacao(
        db,
        conteudo_tipo="questao",
        conteudo_id=outra_questao_id,
        dispositivo_id=art1.id,
        posicao=1,
    )
    db.flush()

    encontrados = dispositivos_da_questao(db, questao_id)

    assert [d.citacao_canonica for d in encontrados] == [
        "Lei 8.429/1992 art. 2",
        "Lei 8.429/1992 art. 1",
    ]


def test_dispositivos_da_questao_vazio_sem_nenhuma_citacao(db: Session) -> None:
    assert dispositivos_da_questao(db, uuid4()) == []
