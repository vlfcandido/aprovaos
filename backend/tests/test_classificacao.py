# O que é: testes do passo 8 da V3 — o léxico por regras (`classificar_por_regras`), o lote
# (`montar_lotes`), a interpretação da resposta da IA (`interpretar_resposta`) e a orquestração
# `classificar` (IA → item a item confere → regras, nunca bloqueia), além de
# `escolher_classificador` (sem chave → regras). Quando ler: ao ajustar o léxico para um edital
# real que ele não cobre, ou ao mudar o fluxo de fallback da classificação.
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from aprovaos.agentes.classificador import MOTIVO_SEM_CHAVE, escolher_classificador
from aprovaos.config import Configuracoes
from aprovaos.dados.modelos import Tenant, Usuario
from aprovaos.dominio.edital import extrair_conteudo_programatico
from aprovaos.motor.curadoria.classificacao import (
    SEM_CORRESPONDENCIA,
    Classificacao,
    ClassificacaoInvalida,
    ClassificadorDeTopico,
    ItemParaClassificar,
    TopicoVocabulario,
    classificar,
    classificar_por_regras,
    interpretar_resposta,
    montar_lotes,
)

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_MD = RAIZ / "docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def vocabulario() -> list[TopicoVocabulario]:
    """O vocabulário real do edital da Linda (36 tópicos, 22 de Direito)."""
    texto = FIXTURE_MD.read_text(encoding="utf-8")
    materias = extrair_conteudo_programatico(texto)
    return [
        TopicoVocabulario(
            slug=topico.slug, materia=materia.slug, texto_original=topico.texto_original
        )
        for materia in materias
        for topico in materia.topicos
    ]


def test_regras_casam_por_lei_citada(vocabulario: list[TopicoVocabulario]) -> None:
    item = ItemParaClassificar(
        numero_item=1,
        comando="Acerca das licitações públicas, julgue o item a seguir.",
        enunciado=(
            "O diálogo competitivo é modalidade de licitação prevista na Lei nº 14.133/2021, "
            "restrita a contratações que envolvam inovação tecnológica ou técnica."
        ),
    )

    resultado = classificar_por_regras([item], vocabulario)

    assert resultado[0].topico_slug == "dir-adm-04-licitacoes-contratos"
    assert resultado[0].confianca == "alta"
    assert "14.133" in resultado[0].evidencia


def test_regras_casam_por_termo(vocabulario: list[TopicoVocabulario]) -> None:
    item = ItemParaClassificar(
        numero_item=2,
        comando="Acerca dos princípios que regem a atuação estatal, julgue o item a seguir.",
        enunciado=(
            "O princípio da impessoalidade veda que o agente público beneficie interesses "
            "pessoais no exercício da função administrativa."
        ),
    )

    resultado = classificar_por_regras([item], vocabulario)

    assert resultado[0].topico_slug == "dir-adm-01-principios-administracao"
    assert resultado[0].confianca == "media"


def test_regras_sem_correspondencia(vocabulario: list[TopicoVocabulario]) -> None:
    item = ItemParaClassificar(
        numero_item=3,
        comando="Acerca de redes de computadores, julgue o item a seguir.",
        enunciado=(
            "O protocolo TCP/IP organiza a comunicação entre dispositivos em camadas, sendo a "
            "camada de transporte responsável pela entrega confiável dos pacotes."
        ),
    )

    resultado = classificar_por_regras([item], vocabulario)

    assert resultado[0].topico_slug is None
    assert resultado[0].confianca == "baixa"
    assert resultado[0].evidencia == SEM_CORRESPONDENCIA


def test_lote_respeita_tamanho() -> None:
    assert montar_lotes(itens=45, tamanho=20) == [20, 20, 5]


def test_interpretar_resposta_do_lote(vocabulario: list[TopicoVocabulario]) -> None:
    slugs_validos = {topico.slug for topico in vocabulario}
    texto = (
        '[{"numero_item": 58, "topico_slug": "dir-adm-04-licitacoes-contratos", '
        '"confianca": "alta", "evidencia": "cita a Lei nº 14.133/2021"}]'
    )

    resultado = interpretar_resposta(texto, slugs_validos)

    assert resultado == [
        Classificacao(
            numero_item=58,
            topico_slug="dir-adm-04-licitacoes-contratos",
            confianca="alta",
            evidencia="cita a Lei nº 14.133/2021",
            origem="ia",
        )
    ]


def test_interpretar_resposta_slug_inventado_levanta_erro(
    vocabulario: list[TopicoVocabulario],
) -> None:
    slugs_validos = {topico.slug for topico in vocabulario}
    texto = (
        '[{"numero_item": 1, "topico_slug": "topico-que-nao-existe", "confianca": "alta", '
        '"evidencia": "..."}]'
    )

    with pytest.raises(ClassificacaoInvalida):
        interpretar_resposta(texto, slugs_validos)


def test_interpretar_resposta_json_invalido_levanta_erro(
    vocabulario: list[TopicoVocabulario],
) -> None:
    slugs_validos = {topico.slug for topico in vocabulario}

    with pytest.raises(ClassificacaoInvalida):
        interpretar_resposta("isto não é JSON", slugs_validos)


class _ClassificadorFalso:
    """Dublê da porta: devolve sempre a resposta dada no construtor."""

    def __init__(self, resposta: list[Classificacao]) -> None:
        self.resposta = resposta

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]
    ) -> list[Classificacao]:
        return self.resposta


class _ClassificadorQueLevanta:
    """Dublê da porta: sempre levanta (simula falha do provedor)."""

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]
    ) -> list[Classificacao]:
        raise RuntimeError("provedor fora do ar")


def test_classificador_falso_e_uma_implementacao_da_porta() -> None:
    assert isinstance(_ClassificadorFalso([]), ClassificadorDeTopico)


@pytest.mark.anyio
async def test_item_ausente_na_resposta_cai_para_regras(
    vocabulario: list[TopicoVocabulario],
) -> None:
    itens = [
        ItemParaClassificar(
            numero_item=1,
            comando="Acerca das licitações públicas, julgue o item a seguir.",
            enunciado="O diálogo competitivo é modalidade prevista na Lei nº 14.133/2021.",
        ),
        ItemParaClassificar(numero_item=2, comando=None, enunciado="Enunciado qualquer."),
    ]
    resposta_ia = [
        Classificacao(
            numero_item=1,
            topico_slug="dir-adm-04-licitacoes-contratos",
            confianca="alta",
            evidencia="cita a Lei nº 14.133/2021, do tópico",
            origem="ia",
        )
    ]

    resultado = await classificar(itens, vocabulario, _ClassificadorFalso(resposta_ia), None)

    assert resultado.classificacoes[0].origem == "ia"
    assert resultado.classificacoes[0].motivo_fallback is None
    assert resultado.classificacoes[1].origem == "regras"
    assert resultado.classificacoes[1].motivo_fallback == "item ausente na resposta do modelo"


@pytest.mark.anyio
async def test_fallback_por_erro_da_ia(vocabulario: list[TopicoVocabulario]) -> None:
    itens = [ItemParaClassificar(numero_item=1, comando=None, enunciado="Enunciado qualquer.")]

    resultado = await classificar(itens, vocabulario, _ClassificadorQueLevanta(), None)

    assert resultado.classificacoes[0].origem == "regras"
    assert resultado.classificacoes[0].motivo_fallback == "erro na IA: RuntimeError"


@pytest.mark.anyio
async def test_sem_classificador_ia_usa_regras_com_motivo(
    vocabulario: list[TopicoVocabulario],
) -> None:
    itens = [ItemParaClassificar(numero_item=1, comando=None, enunciado="Enunciado qualquer.")]

    resultado = await classificar(itens, vocabulario, None, "sem GOOGLE_API_KEY")

    assert resultado.classificacoes[0].origem == "regras"
    assert resultado.classificacoes[0].motivo_fallback == "sem GOOGLE_API_KEY"


def test_sem_chave_vai_para_regras(db: Session, config_teste: Configuracoes) -> None:
    tenant = Tenant(tipo="pf", nome="Linda")
    usuario = Usuario(email="linda@exemplo.com", senha_hash="h", tenant=tenant)
    db.add(usuario)
    db.commit()

    classificador, motivo = escolher_classificador(db, config_teste, usuario)

    assert classificador is None
    assert motivo == MOTIVO_SEM_CHAVE
