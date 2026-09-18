# O que é: testes dos passos 9 e 10 da V2 — porta `AnalistaDeEdital`, implementação por regras,
# `gerar_dna` com fallback (IA → verificação → regras), prompt em arquivo, mensagem com os slugs,
# `interpretar_resposta` e a fábrica do ADK sem chave. Quando ler: ao mudar o fluxo de fallback
# ou o prompt do analista.
import re
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from aprovaos.agentes.analista_de_edital import (
    AnalistaDeEdital,
    AnalistaPorRegras,
    carregar_prompt,
    criar_analista_adk,
    gerar_dna,
    interpretar_resposta,
    montar_mensagem,
)
from aprovaos.config import Configuracoes
from aprovaos.dominio.dna import DnaConcurso, montar_dna_por_regras
from aprovaos.dominio.edital import MateriaExtraida, extrair_conteudo_programatico
from tests.test_dominio_dna import JSON_DA_SKILL

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_MD = RAIZ / "docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def texto() -> str:
    return FIXTURE_MD.read_text(encoding="utf-8")


@pytest.fixture
def materias(texto: str) -> list[MateriaExtraida]:
    return extrair_conteudo_programatico(texto)


@pytest.fixture
def dna_bom(texto: str, materias: list[MateriaExtraida]) -> DnaConcurso:
    return montar_dna_por_regras(texto, materias)


class AnalistaFalso:
    """Dublê da porta: devolve sempre o DNA recebido no construtor."""

    def __init__(self, dna: DnaConcurso) -> None:
        self.dna = dna
        self.chamadas = 0

    async def analisar(self, texto: str, materias: list[MateriaExtraida]) -> DnaConcurso:
        self.chamadas += 1
        return self.dna


class AnalistaQueEstoura:
    """Dublê da porta: falha como um provedor fora do ar."""

    async def analisar(self, texto: str, materias: list[MateriaExtraida]) -> DnaConcurso:
        raise RuntimeError("timeout")


@pytest.mark.anyio
async def test_analista_por_regras_e_uma_implementacao_da_porta(
    texto: str, materias: list[MateriaExtraida]
) -> None:
    analista = AnalistaPorRegras()
    assert isinstance(analista, AnalistaDeEdital)
    assert isinstance(AnalistaFalso(montar_dna_por_regras(texto, materias)), AnalistaDeEdital)
    dna = await analista.analisar(texto, materias)
    assert isinstance(dna, DnaConcurso)
    assert dna == montar_dna_por_regras(texto, materias)


@pytest.mark.anyio
async def test_gerar_dna_sem_ia_usa_regras(
    texto: str, materias: list[MateriaExtraida], dna_bom: DnaConcurso
) -> None:
    resultado = await gerar_dna(
        texto, materias, analista_ia=None, motivo_sem_ia="sem GOOGLE_API_KEY"
    )
    assert resultado.origem == "regras"
    assert resultado.motivo_fallback == "sem GOOGLE_API_KEY"
    assert resultado.dna == dna_bom


@pytest.mark.anyio
async def test_gerar_dna_com_ia_aprovada(
    texto: str, materias: list[MateriaExtraida], dna_bom: DnaConcurso
) -> None:
    analista = AnalistaFalso(dna_bom)
    resultado = await gerar_dna(texto, materias, analista_ia=analista, motivo_sem_ia=None)
    assert resultado.origem == "ia"
    assert resultado.motivo_fallback is None
    assert resultado.dna == dna_bom
    assert analista.chamadas == 1


@pytest.mark.anyio
async def test_gerar_dna_ia_reprovada_cai_para_regras(
    texto: str, materias: list[MateriaExtraida], dna_bom: DnaConcurso
) -> None:
    dna_errado = dna_bom.model_copy(deep=True)
    dna_errado.pesos.materia["lingua-portuguesa"].pct_pontos = 20.0
    resultado = await gerar_dna(
        texto, materias, analista_ia=AnalistaFalso(dna_errado), motivo_sem_ia=None
    )
    assert resultado.origem == "regras"
    assert resultado.motivo_fallback is not None
    assert resultado.motivo_fallback.startswith("DNA da IA reprovado: ")
    assert "soma" in resultado.motivo_fallback
    assert resultado.dna == dna_bom


@pytest.mark.anyio
async def test_gerar_dna_ia_estoura_cai_para_regras(
    texto: str, materias: list[MateriaExtraida], dna_bom: DnaConcurso
) -> None:
    resultado = await gerar_dna(
        texto, materias, analista_ia=AnalistaQueEstoura(), motivo_sem_ia=None
    )
    assert resultado.origem == "regras"
    assert resultado.motivo_fallback == "erro na IA: RuntimeError"
    assert "timeout" not in resultado.motivo_fallback
    assert resultado.dna == dna_bom


def test_prompt_existe_e_transcreve_a_skill() -> None:
    prompt = carregar_prompt()
    for trecho in (
        "Peso real é por pontos",
        "uniforme_no_edital",
        "desconhecido",
        "edital omisso — assumido 1,0",
        "topicos_edital",
    ):
        assert trecho in prompt
    # Prompt estático: nenhum `{nome}` de placeholder; as chaves que existem são do JSON de exemplo.
    assert re.findall(r"\{[a-z_]+\}", prompt) == []


def test_mensagem_lista_os_36_slugs(texto: str, materias: list[MateriaExtraida]) -> None:
    mensagem = montar_mensagem(texto, materias)
    assert texto in mensagem
    linhas = [f"{t.slug} | {m.slug} | {t.texto_original}" for m in materias for t in m.topicos]
    assert len(linhas) == 36
    for linha in linhas:
        assert linha in mensagem
    assert "dir-adm-04-licitacoes-contratos | direito-administrativo | 4. Licitações" in mensagem


def test_interpretar_resposta_valida() -> None:
    assert isinstance(interpretar_resposta(JSON_DA_SKILL), DnaConcurso)
    assert isinstance(interpretar_resposta(f"```json\n{JSON_DA_SKILL}\n```"), DnaConcurso)
    assert isinstance(interpretar_resposta(f"  ```\n{JSON_DA_SKILL}\n```  "), DnaConcurso)
    with pytest.raises(ValidationError):
        interpretar_resposta("{}")


def test_criar_analista_adk_exige_chave(config_teste: Configuracoes) -> None:
    assert config_teste.google_api_key is None
    with pytest.raises(ValueError, match="GOOGLE_API_KEY ausente"):
        criar_analista_adk(config_teste, lambda chamada: None)


def test_criar_analista_adk_com_chave_nao_faz_rede(config_teste: Configuracoes) -> None:
    # Só constrói o agente e o runner; nenhuma chamada sai daqui (a chave é falsa).
    config = config_teste.model_copy(update={"google_api_key": SecretStr("chave-falsa")})
    analista = criar_analista_adk(config, lambda chamada: None)
    assert isinstance(analista, AnalistaDeEdital)


def test_criar_analista_adk_usa_json_mode_sem_output_schema(config_teste: Configuracoes) -> None:
    # Q4 (plano B): o Gemini Developer API rejeita `additionalProperties` dos `dict` do DNA,
    # então o esquema vai no prompt e a resposta é pedida em JSON mode; quem valida é
    # `interpretar_resposta`.
    from google.adk.agents import LlmAgent

    config = config_teste.model_copy(update={"google_api_key": SecretStr("chave-falsa")})
    agente = criar_analista_adk(config, lambda chamada: None).agente
    assert isinstance(agente, LlmAgent)
    assert agente.output_schema is None
    assert agente.output_key is None
    assert agente.generate_content_config is not None
    assert agente.generate_content_config.response_mime_type == "application/json"
    assert agente.generate_content_config.temperature == 0.2
    assert agente.include_contents == "none"
    assert "sem cerca de código, com exatamente estas chaves nesta ordem" in str(agente.instruction)
