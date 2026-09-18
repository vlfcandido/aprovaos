# O que é: teste `llm` do passo 10 da V2 — chama o Gemini de verdade com a fixture PDF e mede se o
# DNA passa em `verificar_dna` (pulado sem GOOGLE_API_KEY). Quando ler: ao rodar
# `GOOGLE_API_KEY=… uv run pytest -q -m llm -s` uma vez por fatia e colar a saída no diário.
import os
from pathlib import Path

import pytest
from pydantic import SecretStr

from aprovaos.agentes.analista_de_edital import criar_analista_adk
from aprovaos.config import Configuracoes
from aprovaos.dominio.dna import verificar_dna
from aprovaos.dominio.edital import extrair_conteudo_programatico
from aprovaos.dominio.pdf import extrair_texto
from aprovaos.roteador.custo import ChamadaLlm

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_PDF = RAIZ / "knowledge/fixtures/editais/edital-assessor-gabinete.pdf"


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
async def test_dna_real_do_fixture(config_com_chave: Configuracoes) -> None:
    texto = extrair_texto(FIXTURE_PDF.read_bytes())
    materias = extrair_conteudo_programatico(texto)
    chamadas: list[ChamadaLlm] = []
    analista = criar_analista_adk(config_com_chave, chamadas.append)

    dna = await analista.analisar(texto, materias)

    # O que o piloto precisa saber: tokens, custo e o que a verificação reprovou (se algo).
    print(f"\nchamada: {chamadas[0].model_dump()}")
    problemas = verificar_dna(dna, materias)
    for problema in problemas:
        print(f"verificar_dna: {problema}")
    assert len(chamadas) == 1
    assert chamadas[0].resultado == "ok"
    assert chamadas[0].modelo == config_com_chave.modelo_dna
    assert chamadas[0].tokens_in is not None and chamadas[0].tokens_in > 0
    assert chamadas[0].custo_brl is not None and chamadas[0].custo_brl > 0
    assert problemas == []
