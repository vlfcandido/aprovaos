# O que é: teste `llm` do passo 8 da V3 — chama o Gemini de verdade com 5 itens reais do caderno
# de Direito da TJ-PA e o vocabulário do fixture de edital (fictício, Fase 4); mede se todo slug
# devolvido está no vocabulário e imprime tokens/custo para o diário. Quando ler: ao rodar
# `GOOGLE_API_KEY=… uv run pytest -q -m llm -s -k classificador` uma vez por fatia (P-27).
import os
from pathlib import Path

import pytest
from pydantic import SecretStr

from aprovaos.agentes.classificador import criar_classificador_adk
from aprovaos.config import Configuracoes
from aprovaos.dominio.edital import extrair_conteudo_programatico
from aprovaos.dominio.pdf import extrair_texto
from aprovaos.dominio.prova import segmentar_cebraspe
from aprovaos.motor.curadoria.classificacao import ItemParaClassificar, TopicoVocabulario
from aprovaos.roteador.custo import ChamadaLlm

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_EDITAL = RAIZ / "knowledge/fixtures/editais/edital-assessor-gabinete.pdf"
FIXTURE_PROVA = (
    RAIZ
    / "knowledge/provas/TJ_PA_25_SERVIDOR"
    / "C15F414E0E91EF109220A73BDF53B232C4466F64770A91E715C56DCB94131F41.pdf"
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def config_com_chave(config_teste: Configuracoes) -> Configuracoes:
    # A chave vem só do ambiente (o hook do conftest já pulou o teste se ela não existir).
    return config_teste.model_copy(
        update={"google_api_key": SecretStr(os.environ["GOOGLE_API_KEY"])}
    )


@pytest.mark.llm
@pytest.mark.anyio
async def test_classifica_lote_real(config_com_chave: Configuracoes) -> None:
    texto_edital = extrair_texto(FIXTURE_EDITAL.read_bytes())
    materias = extrair_conteudo_programatico(texto_edital)
    vocabulario = [
        TopicoVocabulario(
            slug=topico.slug, materia=materia.slug, texto_original=topico.texto_original
        )
        for materia in materias
        for topico in materia.topicos
    ]
    slugs_validos = {topico.slug for topico in vocabulario}

    texto_prova = extrair_texto(FIXTURE_PROVA.read_bytes())
    itens_brutos = segmentar_cebraspe(texto_prova)[:5]
    itens = [
        ItemParaClassificar(
            numero_item=item.numero_item, comando=item.comando, enunciado=item.enunciado
        )
        for item in itens_brutos
    ]

    chamadas: list[ChamadaLlm] = []
    classificador = criar_classificador_adk(config_com_chave, chamadas.append)

    classificacoes, motivos_rejeicao = await classificador.classificar_lote(itens, vocabulario)

    # O que o piloto precisa saber: tokens, custo, e se alguma entrada foi rejeitada (slug fora
    # do vocabulário ou fora do contrato) — `interpretar_resposta` já teria isolado essa entrada
    # sem derrubar as outras.
    print(f"\nchamada: {chamadas[0].model_dump()}")
    for classificacao in classificacoes:
        print(
            f"item {classificacao.numero_item}: {classificacao.topico_slug} "
            f"({classificacao.confianca}) — {classificacao.evidencia}"
        )
    for numero_item, motivo in motivos_rejeicao.items():
        print(f"item {numero_item}: rejeitado — {motivo}")
    assert len(chamadas) == 1
    assert chamadas[0].resultado == "ok"
    assert chamadas[0].modelo == config_com_chave.modelo_classificacao
    assert chamadas[0].tokens_in is not None and chamadas[0].tokens_in > 0
    assert chamadas[0].custo_brl is not None and chamadas[0].custo_brl > 0
    assert len(classificacoes) + len(motivos_rejeicao) == len(itens)
    assert all(
        classificacao.topico_slug is None or classificacao.topico_slug in slugs_validos
        for classificacao in classificacoes
    )
