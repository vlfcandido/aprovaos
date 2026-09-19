# O que é: testes do agente `gerador-de-aula` (fatia 6) — porta, prompt em arquivo, mensagem
# com o dossiê/relacionados/questões, `interpretar_resposta` e a fábrica do ADK sem chave (mesmo
# padrão de `test_gerador_de_justificativa.py`). Quando ler: ao mudar o prompt ou o contrato de
# entrada/saída do agente.
import re

import pytest
from pydantic import SecretStr, ValidationError

from aprovaos.agentes.gerador_de_aula import (
    GeradorDeAula,
    carregar_prompt,
    criar_gerador_adk,
    interpretar_resposta,
    montar_mensagem,
)
from aprovaos.config import Configuracoes
from aprovaos.dominio.aula import (
    ConteudoAula,
    EntradaGeradorAula,
    QuestaoParaAula,
    RelacionadoEntrada,
)
from aprovaos.dominio.dossie import FonteDossie

FONTE = FonteDossie(
    id="F1",
    tipo="norma",
    norma="lei-8429-1992",
    artigo="1",
    citacao_canonica="Lei 8.429/1992 art. 1",
    url="https://planalto.gov.br/lei-8429",
    trecho="Art. 1º Os atos de improbidade administrativa serão punidos na forma desta lei.",
)

ENTRADA_MINIMA = EntradaGeradorAula(
    topico_slug="dir-adm-06-improbidade-administrativa",
    fontes=[FONTE],
    relacionados=[],
    questoes_como_banca=[],
    tempo_alvo_min=5,
)

ENTRADA_COMPLETA = EntradaGeradorAula(
    topico_slug="dir-adm-06-improbidade-administrativa",
    fontes=[FONTE],
    relacionados=[
        RelacionadoEntrada(
            topico_slug="dir-pro-civ-03-atos-processuais",
            dias_atras=6,
            acertos=1,
            total=3,
            trecho_do_dossie_relacionado="Os prazos processuais contam-se em dias úteis.",
        )
    ],
    questoes_como_banca=[
        QuestaoParaAula(
            origem="cebraspe 2024 tj-pa item 57",
            enunciado="O agente que pratica ato de improbidade responde nos termos da lei.",
        )
    ],
    tempo_alvo_min=5,
)

JSON_RESPOSTA = """
{
  "texto_denso": "A improbidade é punida na forma da lei {{Lei 8.429/1992 art. 1}}.",
  "texto_leigo": "A lei pune improbidade.",
  "citacoes": [
    {"canonica": "Lei 8.429/1992 art. 1", "fonte": "F1",
     "trecho": "serão punidos na forma desta lei",
     "frase_da_aula": "A improbidade é punida na forma da lei"}
  ],
  "relacionados": [],
  "como_a_banca_cobra": [],
  "lacunas_declaradas": [],
  "mnemonico": null
}
"""


class GeradorFalso:
    """Dublê da porta: devolve sempre o objeto recebido no construtor."""

    def __init__(self, resposta: ConteudoAula) -> None:
        self.resposta = resposta
        self.chamadas = 0

    async def gerar(self, entrada: EntradaGeradorAula) -> ConteudoAula:
        self.chamadas += 1
        return self.resposta


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_gerador_falso_e_uma_implementacao_da_porta() -> None:
    resposta = interpretar_resposta(JSON_RESPOSTA)
    falso = GeradorFalso(resposta)
    assert isinstance(falso, GeradorDeAula)
    devolvido = await falso.gerar(ENTRADA_MINIMA)
    assert falso.chamadas == 1
    assert devolvido is resposta


def test_prompt_existe_e_fala_do_contrato() -> None:
    prompt = carregar_prompt()
    for trecho in (
        "texto_denso",
        "texto_leigo",
        "citacoes",
        "relacionados",
        "como_a_banca_cobra",
        "lacunas_declaradas",
        "mnemonico",
        "não pode citar dispositivo",
    ):
        assert trecho in prompt
    assert re.findall(r"\{[a-z_]+\}", prompt) == []


def test_mensagem_lista_fontes_relacionados_e_questoes() -> None:
    mensagem = montar_mensagem(ENTRADA_COMPLETA)
    assert "F1 | Lei 8.429/1992 art. 1 |" in mensagem
    assert "dir-pro-civ-03-atos-processuais" in mensagem
    assert "acertou 1 de 3" in mensagem or "1 de 3" in mensagem
    assert "cebraspe 2024 tj-pa item 57" in mensagem
    assert "tempo_alvo_min: 5" in mensagem


def test_mensagem_sem_relacionados_nem_questoes_nao_quebra() -> None:
    mensagem = montar_mensagem(ENTRADA_MINIMA)
    assert "F1 | Lei 8.429/1992 art. 1 |" in mensagem


def test_interpretar_resposta() -> None:
    resultado = interpretar_resposta(JSON_RESPOSTA)
    assert isinstance(resultado, ConteudoAula)
    assert resultado.citacoes[0].canonica == "Lei 8.429/1992 art. 1"
    # tolera cerca de código, como os outros agentes
    resultado_cercado = interpretar_resposta(f"```json\n{JSON_RESPOSTA}\n```")
    assert isinstance(resultado_cercado, ConteudoAula)


def test_interpretar_resposta_invalida_levanta() -> None:
    with pytest.raises(ValidationError):
        interpretar_resposta("{}")


def test_criar_gerador_adk_exige_chave(config_teste: Configuracoes) -> None:
    with pytest.raises(ValueError, match="GOOGLE_API_KEY ausente"):
        criar_gerador_adk(config_teste, lambda chamada: None)


def test_criar_gerador_adk_com_chave_nao_faz_rede(config_teste: Configuracoes) -> None:
    config = config_teste.model_copy(update={"google_api_key": SecretStr("chave-falsa")})
    gerador = criar_gerador_adk(config, lambda chamada: None)
    assert isinstance(gerador, GeradorDeAula)


def test_criar_gerador_adk_usa_json_mode_sem_output_schema(config_teste: Configuracoes) -> None:
    from google.adk.agents import LlmAgent

    config = config_teste.model_copy(update={"google_api_key": SecretStr("chave-falsa")})
    agente = criar_gerador_adk(config, lambda chamada: None).agente
    assert isinstance(agente, LlmAgent)
    assert agente.output_schema is None
    assert agente.generate_content_config is not None
    assert agente.generate_content_config.response_mime_type == "application/json"
    assert agente.include_contents == "none"
