# O que é: testes de `dados/repositorio_veredito.py` (fatia 5) — o histórico append-only de
# tentativas de validação de uma inédita (RF-28: reprovada fica gravada com o motivo). Quando
# ler: ao mexer no repositório ou no comando `motor/gerar_questao.py`.
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Questao
from aprovaos.dados.repositorio_veredito import registrar_veredito, veredictos_da_questao
from aprovaos.dominio.questao import RegraProva
from aprovaos.dominio.validacao_questao import Veredito


def _questao_inedita(db: Session) -> Questao:
    questao = Questao(
        adapter="concursos",
        banca="cebraspe",
        tipo_item="certo_errado",
        comando="Julgue o item.",
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado="Item inédito gerado pelo AprovaOS.",
        gabarito_preliminar=None,
        gabarito="E",
        gabarito_status="definitivo",
        publicavel=False,
        motivo_nao_publicavel="pendente de validação",
        regra_prova=RegraProva(anula_por_erro=False, fonte="inédita — não se aplica").model_dump(
            mode="json"
        ),
        topico=None,
        topico_confianca="alta",
        topico_evidencia="gerada para o tópico",
        origem=None,
        inedita=True,
        documento_id=None,
        hash_dedup="hash-inedita-1",
    )
    db.add(questao)
    db.flush()
    return questao


def test_registrar_veredito_grava_aprovado(db: Session) -> None:
    questao = _questao_inedita(db)
    veredito = Veredito(aprovado=True, motivos=[], validador_versao="v1-lexico", aderencia_pct=0.4)
    linha = registrar_veredito(db, questao.id, veredito)
    assert linha.aprovado is True
    assert linha.motivos == []
    assert linha.validador_versao == "v1-lexico"


def test_registrar_veredito_grava_reprovado_com_motivo(db: Session) -> None:
    questao = _questao_inedita(db)
    veredito = Veredito(
        aprovado=False,
        motivos=["gabarito: resolução independente diverge"],
        validador_versao="v1-lexico",
        aderencia_pct=None,
    )
    linha = registrar_veredito(db, questao.id, veredito)
    assert linha.aprovado is False
    assert linha.motivos == ["gabarito: resolução independente diverge"]


def test_veredictos_da_questao_devolve_historico_em_ordem(db: Session) -> None:
    questao = _questao_inedita(db)
    registrar_veredito(
        db,
        questao.id,
        Veredito(aprovado=False, motivos=["m1"], validador_versao="v1", aderencia_pct=None),
    )
    registrar_veredito(
        db,
        questao.id,
        Veredito(aprovado=True, motivos=[], validador_versao="v1", aderencia_pct=0.5),
    )
    historico = veredictos_da_questao(db, questao.id)
    assert len(historico) == 2
    assert historico[0].motivos == ["m1"]
    assert historico[1].aprovado is True


def test_veredictos_da_questao_sem_historico_devolve_vazio(db: Session) -> None:
    questao = _questao_inedita(db)
    assert veredictos_da_questao(db, questao.id) == []
