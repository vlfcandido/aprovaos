# O que é: testes do comando `motor/gerar_questao.py` (fatia 5) — gera e valida inéditas de um
# tópico via `gerador-de-questao` + `validador-de-questao` (dois agentes falsos, sem rede),
# grava a `Questao` sempre (aprovada ou reprovada, RF-28) e o histórico em `veredito_questao`.
# Quando ler: ao mudar o pipeline do comando ou a regra de quando um tópico fica sem geração
# nesta rodada.
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import DossieTopico, Questao, Topico, VereditoQuestao
from aprovaos.dados.repositorio_veredito import veredictos_da_questao
from aprovaos.dominio.questao import RegraProva
from aprovaos.dominio.questao_inedita import (
    EntradaGeradorQuestao,
    QuestaoGerada,
    montar_plano_do_lote,
)
from aprovaos.dominio.validacao_questao import EntradaValidadorQuestao, ResolucaoValidador
from aprovaos.motor.gerar_questao import gerar_questoes_topico

FONTE_TRECHO = (
    "Art. 71. O controle externo, a cargo do Congresso Nacional, será exercido com o auxílio "
    "do Tribunal de Contas da União, ao qual compete: I - apreciar as contas prestadas "
    "anualmente pelo Presidente da República, mediante parecer prévio."
)

REGRA_PROVA = RegraProva(anula_por_erro=False, fonte="inédita — sem regra do DNA")


def _topico(db: Session, slug: str) -> Topico:
    topico = Topico(materia="direito-constitucional", nome=slug, slug=slug)
    db.add(topico)
    db.flush()
    return topico


def _dossie(db: Session, topico: Topico) -> DossieTopico:
    dossie = DossieTopico(
        topico_id=topico.id,
        versao=1,
        gerado_em=agora_utc(),
        conteudo="conteúdo",
        fontes=[
            {
                "id": "F1",
                "tipo": "norma",
                "citacao_canonica": "CF/88 art. 71 I",
                "url": "https://planalto.gov.br/cf88",
                "trecho": FONTE_TRECHO,
                "vigente": True,
            }
        ],
        bibliografia=[],
        log_buscas=[],
    )
    db.add(dossie)
    db.flush()
    return dossie


def _item_eco(entrada: EntradaGeradorQuestao) -> QuestaoGerada:
    """Um item conforme, ecoando o mecanismo/gabarito prescritos pela entrada."""
    return QuestaoGerada(
        tipo_item=entrada.tipo_item,
        banca_alvo=entrada.banca_alvo,
        comando="Julgue o item a seguir.",
        enunciado="O TCU aprecia as contas do Presidente da República mediante parecer prévio.",
        alternativas=None,
        gabarito=entrada.gabarito_alvo,
        fontes=[entrada.fontes[0].id],
        trecho_que_decide="apreciar as contas prestadas anualmente pelo Presidente da República",
        justificativa_certo="Se dissesse 'aprecia', estaria certo.",
        justificativa_errado="O TCU aprecia; quem julga é o Congresso.",
        mecanismo=entrada.mecanismo_alvo,
        original_de_referencia="cebraspe 2024 tce-xx item 57",
        topico_slug=entrada.topico_slug,
        aderencia_medida=entrada.aderencia_medida,
    )


class GeradorEco:
    """Dublê do gerador que sempre ecoa o mecanismo/gabarito prescritos (nunca diverge do plano)."""

    def __init__(self) -> None:
        self.chamadas = 0

    async def gerar(self, entrada: EntradaGeradorQuestao) -> QuestaoGerada:
        self.chamadas += 1
        return _item_eco(entrada)


class ValidadorFalso:
    """Dublê do validador: uma resolução (ou exceção) por chamada, na ordem dada."""

    def __init__(self, respostas: list[ResolucaoValidador | Exception]) -> None:
        self.respostas = respostas
        self.chamadas = 0

    async def resolver(self, entrada: EntradaValidadorQuestao) -> ResolucaoValidador:
        resposta = self.respostas[self.chamadas]
        self.chamadas += 1
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_sem_topico_nao_gera_nada(db: Session) -> None:
    relatorio = await gerar_questoes_topico(
        db,
        "topico-que-nao-existe",
        2,
        "certo_errado",
        "cebraspe",
        REGRA_PROVA,
        GeradorEco(),
        ValidadorFalso([]),
        espera_entre_chamadas_s=0.0,
    )
    assert relatorio.status == "sem_topico"
    assert relatorio.itens == []


@pytest.mark.anyio
async def test_sem_dossie_nao_gera_nada(db: Session) -> None:
    topico = _topico(db, "dir-const-06-sem-dossie")
    relatorio = await gerar_questoes_topico(
        db,
        topico.slug,
        2,
        "certo_errado",
        "cebraspe",
        REGRA_PROVA,
        GeradorEco(),
        ValidadorFalso([]),
        espera_entre_chamadas_s=0.0,
    )
    assert relatorio.status == "sem_dossie"


@pytest.mark.anyio
async def test_sem_ia_nao_gera_nada(db: Session) -> None:
    topico = _topico(db, "dir-const-07-sem-ia")
    _dossie(db, topico)
    relatorio = await gerar_questoes_topico(
        db,
        topico.slug,
        2,
        "certo_errado",
        "cebraspe",
        REGRA_PROVA,
        None,
        None,
        espera_entre_chamadas_s=0.0,
    )
    assert relatorio.status == "sem_ia"


@pytest.mark.anyio
async def test_lote_conforme_aprova_todos_e_grava_questoes(db: Session) -> None:
    topico = _topico(db, "dir-const-08-fiscalizacao")
    _dossie(db, topico)

    plano = montar_plano_do_lote(n_pedido=2, originais_recebidos=0, tipo_item="certo_errado")
    validador = ValidadorFalso([ResolucaoValidador(gabarito=i.gabarito) for i in plano.itens])

    relatorio = await gerar_questoes_topico(
        db,
        topico.slug,
        2,
        "certo_errado",
        "cebraspe",
        REGRA_PROVA,
        GeradorEco(),
        validador,
        espera_entre_chamadas_s=0.0,
    )

    assert relatorio.status == "gerado"
    assert len(relatorio.itens) == 2
    assert relatorio.divergencias_do_plano == []
    assert all(item.status == "aprovado" for item in relatorio.itens)

    questoes = list(db.scalars(select(Questao).where(Questao.topico_id == topico.id)))
    assert len(questoes) == 2
    assert all(q.inedita is True and q.publicavel is True and q.origem is None for q in questoes)

    for item in relatorio.itens:
        historico = veredictos_da_questao(db, UUID(item.questao_id))
        assert len(historico) == 1
        assert historico[0].aprovado is True


@pytest.mark.anyio
async def test_gabarito_divergente_reprova_mas_grava_com_motivo(db: Session) -> None:
    topico = _topico(db, "dir-const-09-divergencia")
    _dossie(db, topico)

    plano = montar_plano_do_lote(n_pedido=1, originais_recebidos=0, tipo_item="certo_errado")
    gabarito_divergente = "E" if plano.itens[0].gabarito == "C" else "C"
    validador = ValidadorFalso([ResolucaoValidador(gabarito=gabarito_divergente)])

    relatorio = await gerar_questoes_topico(
        db,
        topico.slug,
        1,
        "certo_errado",
        "cebraspe",
        REGRA_PROVA,
        GeradorEco(),
        validador,
        espera_entre_chamadas_s=0.0,
    )

    assert relatorio.itens[0].status == "reprovado"
    assert any("gabarito" in m for m in relatorio.itens[0].motivos)

    questao = db.get(Questao, UUID(relatorio.itens[0].questao_id))
    assert questao is not None
    assert questao.publicavel is False
    assert questao.motivo_nao_publicavel is not None
    assert "gabarito" in questao.motivo_nao_publicavel


@pytest.mark.anyio
async def test_falha_do_gerador_nao_grava_questao_e_segue_o_lote(db: Session) -> None:
    topico = _topico(db, "dir-const-10-falha-gerador")
    _dossie(db, topico)

    plano = montar_plano_do_lote(n_pedido=2, originais_recebidos=0, tipo_item="certo_errado")

    class _GeradorMisto:
        def __init__(self) -> None:
            self.chamadas = 0

        async def gerar(self, entrada: EntradaGeradorQuestao) -> QuestaoGerada:
            self.chamadas += 1
            if self.chamadas == 1:
                raise RuntimeError("timeout")
            return _item_eco(entrada)

    validador = ValidadorFalso([ResolucaoValidador(gabarito=plano.itens[1].gabarito)])

    relatorio = await gerar_questoes_topico(
        db,
        topico.slug,
        2,
        "certo_errado",
        "cebraspe",
        REGRA_PROVA,
        _GeradorMisto(),
        validador,
        espera_entre_chamadas_s=0.0,
    )

    assert len(relatorio.itens) == 2
    assert relatorio.itens[0].status == "erro"
    assert relatorio.itens[0].questao_id is None
    assert "erro na IA" in relatorio.itens[0].motivos[0]
    assert relatorio.itens[1].status == "aprovado"

    questoes = list(db.scalars(select(Questao).where(Questao.topico_id == topico.id)))
    assert len(questoes) == 1


@pytest.mark.anyio
async def test_falha_do_validador_reprova_e_registra_o_motivo(db: Session) -> None:
    topico = _topico(db, "dir-const-11-falha-validador")
    _dossie(db, topico)

    validador = ValidadorFalso([RuntimeError("cota estourada")])

    relatorio = await gerar_questoes_topico(
        db,
        topico.slug,
        1,
        "certo_errado",
        "cebraspe",
        REGRA_PROVA,
        GeradorEco(),
        validador,
        espera_entre_chamadas_s=0.0,
    )

    assert relatorio.itens[0].status == "reprovado"
    assert "erro na IA" in relatorio.itens[0].motivos[0]
    assert relatorio.itens[0].questao_id is not None

    questao = db.get(Questao, UUID(relatorio.itens[0].questao_id))
    assert questao is not None
    assert questao.publicavel is False


@pytest.mark.anyio
async def test_divergencia_do_plano_e_reportada(db: Session) -> None:
    topico = _topico(db, "dir-const-12-divergencia-plano")
    _dossie(db, topico)

    class _GeradorTeimoso:
        """Ignora o mecanismo/gabarito prescritos — sempre devolve o mesmo, quebrando o plano."""

        def __init__(self) -> None:
            self.chamadas = 0

        async def gerar(self, entrada: EntradaGeradorQuestao) -> QuestaoGerada:
            self.chamadas += 1
            item = _item_eco(entrada)
            # Enunciados distintos (mesma frase, uma palavra a mais no fim) só para não colidir
            # em `hash_dedup` — o que este teste audita é mecanismo/gabarito ignorados, não
            # deduplicação; mantém uma única sentença para não disparar a regra de forma.
            enunciado = item.enunciado.rstrip(".") + f" no caso {self.chamadas}."
            item = item.model_copy(update={"enunciado": enunciado})
            return item.model_copy(update={"mecanismo": "literal", "gabarito": "C"})

    validador = ValidadorFalso([ResolucaoValidador(gabarito="C"), ResolucaoValidador(gabarito="C")])

    relatorio = await gerar_questoes_topico(
        db,
        topico.slug,
        2,
        "certo_errado",
        "cebraspe",
        REGRA_PROVA,
        _GeradorTeimoso(),
        validador,
        espera_entre_chamadas_s=0.0,
    )

    assert relatorio.divergencias_do_plano != []


@pytest.mark.anyio
async def test_registra_veredito_mesmo_quando_reprovado(db: Session) -> None:
    topico = _topico(db, "dir-const-13-historico")
    _dossie(db, topico)
    plano = montar_plano_do_lote(n_pedido=1, originais_recebidos=0, tipo_item="certo_errado")
    gabarito_divergente = "E" if plano.itens[0].gabarito == "C" else "C"
    validador = ValidadorFalso([ResolucaoValidador(gabarito=gabarito_divergente)])

    await gerar_questoes_topico(
        db,
        topico.slug,
        1,
        "certo_errado",
        "cebraspe",
        REGRA_PROVA,
        GeradorEco(),
        validador,
        espera_entre_chamadas_s=0.0,
    )

    historico = list(db.scalars(select(VereditoQuestao)))
    assert len(historico) == 1
    assert historico[0].aprovado is False
    assert historico[0].motivos != []
