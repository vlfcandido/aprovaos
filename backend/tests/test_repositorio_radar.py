# O que é: testes do passo 3 do plano `docs/fatias/1b-radar-e-conta.md` — `sincronizar` nunca
# duplica, nunca apaga e carimba `ultimo_visto_em` em tudo que veio. Quando ler: ao mexer em
# `aprovaos/dados/repositorio_radar.py`.
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from aprovaos.dados.modelos import ConcursoRadar
from aprovaos.dados.repositorio_radar import (
    URL_DETALHE_CEBRASPE,
    buscar_por_evento_url,
    listar,
    obter_ou_criar_fonte,
    sincronizar,
)
from aprovaos.dominio.radar import ConcursoDoRadar
from aprovaos.motor.fontes.cebraspe import URL_DETALHE

T1 = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
T2 = datetime(2026, 9, 19, 16, 0, tzinfo=UTC)


def test_url_detalhe_bate_com_a_fonte_cebraspe() -> None:
    """O literal duplicado em `repositorio_radar.py` não pode divergir do de `motor/fontes`."""
    assert URL_DETALHE_CEBRASPE == URL_DETALHE


def _concurso(evento_url: str = "AGEPAR_PR_26", **sobrescritas: object) -> ConcursoDoRadar:
    base: dict[str, object] = {
        "evento_url": evento_url,
        "nome": "AGEPAR PR 26",
        "ano": 2026,
        "fase": "em_andamento",
        "uf": "PR",
        "vagas": 23,
        "salario_max_brl": Decimal("9975"),
        "periodo_inscricao_texto": None,
        "inscricao_inicio": None,
        "inscricao_fim": None,
        "lacunas": ["data da prova não publicada na API"],
    }
    base.update(sobrescritas)
    return ConcursoDoRadar.model_validate(base)


def test_sincronizar_insere_o_que_e_novo(db: Session) -> None:
    fonte = obter_ou_criar_fonte(db, "cebraspe", "Cebraspe", "https://apis.cebraspe.org.br/x")

    relatorio = sincronizar(db, fonte, [_concurso()], T1)

    assert relatorio.novos == 1
    assert relatorio.atualizados == 0
    assert relatorio.inalterados == 0
    linha = buscar_por_evento_url(db, "AGEPAR_PR_26")
    assert linha is not None
    assert linha.primeiro_visto_em == T1
    assert linha.ultimo_visto_em == T1
    assert linha.url_evento == URL_DETALHE.format(eventoURL="AGEPAR_PR_26")
    assert linha.bruto["nome"] == "AGEPAR PR 26"


def test_sincronizar_duas_vezes_nao_duplica_nem_muda_primeiro_visto(db: Session) -> None:
    fonte = obter_ou_criar_fonte(db, "cebraspe", "Cebraspe", "https://apis.cebraspe.org.br/x")
    sincronizar(db, fonte, [_concurso()], T1)

    relatorio = sincronizar(db, fonte, [_concurso()], T2)

    assert relatorio.novos == 0
    assert relatorio.atualizados == 0
    assert relatorio.inalterados == 1
    linhas = listar(db)
    assert len(linhas) == 1
    assert linhas[0].primeiro_visto_em == T1
    assert linhas[0].ultimo_visto_em == T2


def test_concurso_que_muda_de_fase_e_atualizado_mantendo_a_identidade(db: Session) -> None:
    fonte = obter_ou_criar_fonte(db, "cebraspe", "Cebraspe", "https://apis.cebraspe.org.br/x")
    sincronizar(db, fonte, [_concurso(fase="em_andamento")], T1)

    relatorio = sincronizar(db, fonte, [_concurso(fase="encerrado")], T2)

    assert relatorio.atualizados == 1
    linha = buscar_por_evento_url(db, "AGEPAR_PR_26")
    assert linha is not None
    assert linha.fase == "encerrado"
    assert linha.primeiro_visto_em == T1
    assert linha.ultimo_visto_em == T2


def test_concurso_que_some_da_fonte_continua_no_catalogo(db: Session) -> None:
    """Um concurso ausente da rodada seguinte não é apagado — só não avança `ultimo_visto_em`."""
    fonte = obter_ou_criar_fonte(db, "cebraspe", "Cebraspe", "https://apis.cebraspe.org.br/x")
    sincronizar(db, fonte, [_concurso("AGEPAR_PR_26"), _concurso("AGU_26_ESTAGIARIO")], T1)

    sincronizar(db, fonte, [_concurso("AGEPAR_PR_26")], T2)

    linhas = {linha.evento_url: linha for linha in listar(db)}
    assert set(linhas) == {"AGEPAR_PR_26", "AGU_26_ESTAGIARIO"}
    assert linhas["AGEPAR_PR_26"].ultimo_visto_em == T2
    assert linhas["AGU_26_ESTAGIARIO"].ultimo_visto_em == T1


def test_listar_filtra_por_fase_e_uf(db: Session) -> None:
    fonte = obter_ou_criar_fonte(db, "cebraspe", "Cebraspe", "https://apis.cebraspe.org.br/x")
    sincronizar(
        db,
        fonte,
        [
            _concurso("AGEPAR_PR_26", fase="em_andamento", uf="PR"),
            _concurso("SEFAZ_AL_26", fase="inscricoes_abertas", uf="AL", nome="SEFAZ AL 26"),
        ],
        T1,
    )

    assert [c.evento_url for c in listar(db, fase="em_andamento")] == ["AGEPAR_PR_26"]
    assert [c.evento_url for c in listar(db, uf="AL")] == ["SEFAZ_AL_26"]


def test_obter_ou_criar_fonte_e_idempotente(db: Session) -> None:
    primeira = obter_ou_criar_fonte(db, "cebraspe", "Cebraspe", "https://apis.cebraspe.org.br/x")
    segunda = obter_ou_criar_fonte(db, "cebraspe", "Cebraspe", "https://apis.cebraspe.org.br/x")

    assert primeira.id == segunda.id


def test_buscar_por_evento_url_inexistente_devolve_none(db: Session) -> None:
    assert buscar_por_evento_url(db, "NAO_EXISTE") is None


def test_bruto_e_a_ultima_leitura_apos_atualizacao(db: Session) -> None:
    fonte = obter_ou_criar_fonte(db, "cebraspe", "Cebraspe", "https://apis.cebraspe.org.br/x")
    sincronizar(db, fonte, [_concurso(vagas=23)], T1)

    sincronizar(db, fonte, [_concurso(vagas=30)], T2)

    linha = buscar_por_evento_url(db, "AGEPAR_PR_26")
    assert linha is not None
    assert linha.vagas == 30
    assert linha.bruto["vagas"] == 30


def test_concurso_radar_e_tabela_global_sem_tenant(db: Session) -> None:
    """`ConcursoRadar` não tem `tenant_id` — o catálogo é público (plano §4)."""
    assert not hasattr(ConcursoRadar, "tenant_id")
