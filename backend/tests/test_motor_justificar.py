# O que é: testes do passo 5 da fundação jurídica — `motor.justificar.justificar_topico`: gera
# a justificativa das questões publicáveis de um tópico com um gerador falso (sem rede), valida
# mecanicamente e grava só o que passou. Quando ler: ao mudar o pipeline do comando ou a regra
# de quando uma questão fica sem justificativa nesta rodada.
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Alternativa, Documento, Questao, Topico
from aprovaos.dados.repositorio_questao import salvar_questoes
from aprovaos.dominio.justificativa import (
    Afirmacao,
    JustificativaCertoErrado,
    JustificativaMultiplaEscolha,
    JustificativaPorAlternativa,
    QuestaoParaJustificar,
)
from aprovaos.dominio.questao import (
    AlternativaCurada,
    Origem,
    QuestaoCurada,
    RegraProva,
    hash_dedup,
)
from aprovaos.motor.dossie import SLUG_IMPROBIDADE, construir_dossie_improbidade
from aprovaos.motor.justificar import justificar_topico
from aprovaos.motor.ligar_por_topico import ligar_por_topico

DISPOSITIVO_CANONICO = "Lei 8.429/1992 art. 1"


def _topico_improbidade(db: Session) -> Topico:
    topico = Topico(materia="direito-administrativo", nome="Improbidade", slug=SLUG_IMPROBIDADE)
    db.add(topico)
    db.flush()
    return topico


def _documento(db: Session) -> Documento:
    hash_ = uuid4().hex
    documento = Documento(
        tipo="prova", hash=hash_, caminho=f"{hash_}.pdf", baixado_em=agora_utc(), metadados={}
    )
    db.add(documento)
    db.flush()
    return documento


def _origem(documento_id: str, numero_item: int) -> Origem:
    return Origem(
        banca="cebraspe",
        orgao="TJ-PA",
        cargo="Analista",
        ano=2025,
        numero_item=numero_item,
        tipo_caderno=None,
        url_prova="https://cdn.cebraspe.org.br/prova.pdf",
        documento_id=documento_id,
    )


def _questao_certo_errado(documento_id: str, numero_item: int, enunciado: str) -> QuestaoCurada:
    return QuestaoCurada(
        banca="cebraspe",
        numero_item=numero_item,
        comando="Julgue o item a seguir.",
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado=enunciado,
        gabarito_preliminar=None,
        gabarito="E",
        gabarito_status="definitivo",
        publicavel=True,
        motivo_nao_publicavel=None,
        regra_prova=RegraProva(anula_por_erro=True, fonte="instrução do caderno"),
        topico_slug=SLUG_IMPROBIDADE,
        topico_confianca="alta",
        topico_evidencia="teste",
        origem=_origem(documento_id, numero_item),
        hash_dedup=hash_dedup(enunciado),
    )


def _questao_multipla_escolha(documento_id: str, numero_item: int, enunciado: str) -> QuestaoCurada:
    alternativas = [
        AlternativaCurada(letra=letra, texto=f"texto {letra}", correta=letra == "B")
        for letra in "ABCDE"
    ]
    return QuestaoCurada(
        banca="cebraspe",
        tipo_item="multipla_escolha",
        numero_item=numero_item,
        comando=None,
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado=enunciado,
        alternativas=alternativas,
        gabarito_preliminar=None,
        gabarito="B",
        gabarito_status="definitivo",
        publicavel=True,
        motivo_nao_publicavel=None,
        regra_prova=RegraProva(anula_por_erro=False, fonte="convenção Cebraspe A–E"),
        topico_slug=SLUG_IMPROBIDADE,
        topico_confianca="alta",
        topico_evidencia="teste",
        origem=_origem(documento_id, numero_item),
        hash_dedup=hash_dedup(enunciado),
    )


def _afirmacao(dispositivo: str, trecho: str, texto: str = "frase de exemplo") -> Afirmacao:
    return Afirmacao(texto=texto, dispositivo=dispositivo, trecho_que_decide=trecho)


class GeradorFalso:
    """Dublê da porta: devolve a resposta preparada por questão (por `enunciado`), na ordem."""

    def __init__(
        self, respostas: dict[str, JustificativaCertoErrado | JustificativaMultiplaEscolha]
    ) -> None:
        self._respostas = respostas
        self.chamadas: list[str] = []

    async def gerar(
        self, questao: QuestaoParaJustificar
    ) -> JustificativaCertoErrado | JustificativaMultiplaEscolha:
        self.chamadas.append(questao.enunciado)
        return self._respostas[questao.enunciado]


class GeradorQueEstoura:
    """Dublê da porta: falha como um provedor fora do ar — nunca deve derrubar o comando."""

    async def gerar(self, questao: QuestaoParaJustificar) -> JustificativaCertoErrado:
        raise RuntimeError("indisponível")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _preparar_base_com_uma_questao_certo_errado(db: Session) -> tuple[str, Questao]:
    _topico_improbidade(db)
    construir_dossie_improbidade(db, hoje=date(2026, 9, 19))
    documento = _documento(db)
    enunciado = "Os atos de improbidade administrativa não se sujeitam a punição."
    salvar_questoes(db, [_questao_certo_errado(str(documento.id), 1, enunciado)])
    db.flush()
    ligar_por_topico(db)
    db.flush()
    questao = db.scalars(select(Questao)).one()
    return enunciado, questao


@pytest.mark.anyio
async def test_justifica_e_grava_quando_aprovado(db: Session) -> None:
    enunciado, questao = _preparar_base_com_uma_questao_certo_errado(db)
    resposta = JustificativaCertoErrado(
        afirmacoes_certo=[
            _afirmacao(DISPOSITIVO_CANONICO, "tutelará a probidade na organização do Estado")
        ],
        afirmacoes_errado=[
            _afirmacao(DISPOSITIVO_CANONICO, "tutelará a probidade na organização do Estado")
        ],
    )
    gerador = GeradorFalso({enunciado: resposta})

    relatorio = await justificar_topico(
        db, SLUG_IMPROBIDADE, gerador, None, espera_entre_chamadas_s=0.0
    )
    db.commit()

    assert relatorio.elegiveis == 1
    assert relatorio.sem_dispositivo == 0
    assert relatorio.geradas == 1
    assert relatorio.aprovadas == 1
    assert relatorio.reprovadas == []
    db.refresh(questao)
    assert questao.justificativa_certo is not None
    assert "[Lei 8.429/1992 art. 1]" in questao.justificativa_certo
    assert questao.justificativa_errado is not None


@pytest.mark.anyio
async def test_nao_grava_quando_validador_reprova(db: Session) -> None:
    enunciado, questao = _preparar_base_com_uma_questao_certo_errado(db)
    resposta_ruim = JustificativaCertoErrado(
        afirmacoes_certo=[_afirmacao(DISPOSITIVO_CANONICO, "frase que a lei nunca disse")],
        afirmacoes_errado=[
            _afirmacao(DISPOSITIVO_CANONICO, "tutelará a probidade na organização do Estado")
        ],
    )
    gerador = GeradorFalso({enunciado: resposta_ruim})

    relatorio = await justificar_topico(
        db, SLUG_IMPROBIDADE, gerador, None, espera_entre_chamadas_s=0.0
    )
    db.commit()

    assert relatorio.geradas == 1
    assert relatorio.aprovadas == 0
    assert len(relatorio.reprovadas) == 1
    assert any("não existe literalmente" in m for m in relatorio.reprovadas[0].motivos)
    db.refresh(questao)
    assert questao.justificativa_certo is None
    assert questao.justificativa_errado is None


@pytest.mark.anyio
async def test_questao_sem_dispositivo_ligado_nao_gera_nada(db: Session) -> None:
    _topico_improbidade(db)
    # sem `construir_dossie_improbidade`/`ligar_por_topico`: nenhum dispositivo ligado.
    documento = _documento(db)
    enunciado = "Enunciado qualquer, sem dossiê construído."
    salvar_questoes(db, [_questao_certo_errado(str(documento.id), 1, enunciado)])
    db.commit()

    gerador = GeradorFalso({})
    relatorio = await justificar_topico(
        db, SLUG_IMPROBIDADE, gerador, None, espera_entre_chamadas_s=0.0
    )

    assert relatorio.elegiveis == 1
    assert relatorio.sem_dispositivo == 1
    assert relatorio.geradas == 0
    assert gerador.chamadas == []


@pytest.mark.anyio
async def test_sem_ia_disponivel_nao_gera_nada_e_nao_quebra(db: Session) -> None:
    _enunciado, _questao = _preparar_base_com_uma_questao_certo_errado(db)

    relatorio = await justificar_topico(
        db, SLUG_IMPROBIDADE, None, "sem GOOGLE_API_KEY", espera_entre_chamadas_s=0.0
    )

    assert relatorio.elegiveis == 1
    assert relatorio.sem_ia == 1
    assert relatorio.geradas == 0


@pytest.mark.anyio
async def test_erro_do_provedor_em_uma_questao_nao_derruba_o_comando(db: Session) -> None:
    _enunciado, _questao = _preparar_base_com_uma_questao_certo_errado(db)

    relatorio = await justificar_topico(
        db, SLUG_IMPROBIDADE, GeradorQueEstoura(), None, espera_entre_chamadas_s=0.0
    )

    assert relatorio.elegiveis == 1
    assert len(relatorio.reprovadas) == 1
    assert "erro na IA: RuntimeError" in relatorio.reprovadas[0].motivos[0]


@pytest.mark.anyio
async def test_questao_ja_justificada_nao_e_regerada(db: Session) -> None:
    enunciado, questao = _preparar_base_com_uma_questao_certo_errado(db)
    resposta = JustificativaCertoErrado(
        afirmacoes_certo=[
            _afirmacao(DISPOSITIVO_CANONICO, "tutelará a probidade na organização do Estado")
        ],
        afirmacoes_errado=[
            _afirmacao(DISPOSITIVO_CANONICO, "tutelará a probidade na organização do Estado")
        ],
    )
    gerador = GeradorFalso({enunciado: resposta})
    await justificar_topico(db, SLUG_IMPROBIDADE, gerador, None, espera_entre_chamadas_s=0.0)
    db.commit()

    segunda_rodada = await justificar_topico(
        db, SLUG_IMPROBIDADE, gerador, None, espera_entre_chamadas_s=0.0
    )

    assert gerador.chamadas == [enunciado]  # só a primeira rodada chamou
    assert segunda_rodada.geradas == 0


@pytest.mark.anyio
async def test_multipla_escolha_grava_as_cinco_alternativas(db: Session) -> None:
    _topico_improbidade(db)
    construir_dossie_improbidade(db, hoje=date(2026, 9, 19))
    documento = _documento(db)
    enunciado = "Sobre a Lei nº 8.429/1992, é correto afirmar que:"
    salvar_questoes(db, [_questao_multipla_escolha(str(documento.id), 1, enunciado)])
    db.flush()
    ligar_por_topico(db)
    db.flush()
    questao = db.scalars(select(Questao)).one()

    resposta = JustificativaMultiplaEscolha(
        alternativas=[
            JustificativaPorAlternativa(
                letra=letra,
                afirmacoes=[
                    _afirmacao(
                        DISPOSITIVO_CANONICO, "tutelará a probidade na organização do Estado"
                    )
                ],
            )
            for letra in "ABCDE"
        ]
    )
    gerador = GeradorFalso({enunciado: resposta})

    relatorio = await justificar_topico(
        db, SLUG_IMPROBIDADE, gerador, None, espera_entre_chamadas_s=0.0
    )
    db.commit()

    assert relatorio.aprovadas == 1
    alternativas = db.scalars(select(Alternativa).where(Alternativa.questao_id == questao.id)).all()
    assert all(a.justificativa is not None for a in alternativas)
