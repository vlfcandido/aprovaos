# O que é: testes do agente `gerador-de-questao` (fatia 5) — porta, prompt em arquivo, mensagem
# com o dossiê/originais/mecanismo-alvo/gabarito-alvo, `interpretar_resposta` e a fábrica do ADK
# sem chave (mesmo padrão de `test_gerador_de_aula.py`). Quando ler: ao mudar o prompt ou o
# contrato de entrada/saída do agente.
import re

import pytest
from pydantic import SecretStr, ValidationError

from aprovaos.agentes.gerador_de_questao import (
    GeradorDeQuestao,
    carregar_prompt,
    criar_gerador_adk,
    interpretar_resposta,
    montar_mensagem,
)
from aprovaos.config import Configuracoes
from aprovaos.dominio.dossie import FonteDossie
from aprovaos.dominio.questao_inedita import (
    EntradaGeradorQuestao,
    OriginalParaGerador,
    QuestaoGerada,
)

FONTE = FonteDossie(
    id="F1",
    tipo="norma",
    norma="lei-8429-1992",
    artigo="1",
    citacao_canonica="Lei 8.429/1992 art. 1",
    url="https://planalto.gov.br/lei-8429",
    trecho="Art. 1º Os atos de improbidade administrativa serão punidos na forma desta lei.",
)

ENTRADA = EntradaGeradorQuestao(
    topico_slug="dir-adm-06-improbidade-administrativa",
    banca_alvo="cebraspe",
    tipo_item="certo_errado",
    fontes=[FONTE],
    originais=[
        OriginalParaGerador(
            enunciado="Os atos de improbidade são punidos na forma da lei.", gabarito="C"
        )
    ],
    mecanismo_alvo="troca_de_verbo",
    gabarito_alvo="E",
    aderencia_medida=False,
)

JSON_RESPOSTA = """
{
  "tipo_item": "certo_errado", "banca_alvo": "cebraspe",
  "comando": "Acerca da improbidade administrativa, julgue o item a seguir.",
  "enunciado": "Os atos de improbidade administrativa serão perdoados na forma desta lei.",
  "alternativas": null,
  "gabarito": "E",
  "fontes": ["F1"],
  "trecho_que_decide": "serão punidos na forma desta lei",
  "justificativa_certo": "Se dissesse 'punidos', estaria certo.",
  "justificativa_errado": "A lei diz 'punidos', não 'perdoados'.",
  "mecanismo": "troca_de_verbo",
  "original_de_referencia": "cebraspe 2024 tce-xx item 1",
  "topico_slug": "dir-adm-06-improbidade-administrativa",
  "aderencia_medida": false
}
"""


class GeradorFalso:
    """Dublê da porta: devolve sempre o objeto recebido no construtor."""

    def __init__(self, resposta: QuestaoGerada) -> None:
        self.resposta = resposta
        self.chamadas = 0

    async def gerar(self, entrada: EntradaGeradorQuestao) -> QuestaoGerada:
        self.chamadas += 1
        return self.resposta


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_gerador_falso_e_uma_implementacao_da_porta() -> None:
    resposta = interpretar_resposta(JSON_RESPOSTA)
    falso = GeradorFalso(resposta)
    assert isinstance(falso, GeradorDeQuestao)
    devolvido = await falso.gerar(ENTRADA)
    assert falso.chamadas == 1
    assert devolvido is resposta


def test_prompt_existe_e_fala_do_contrato() -> None:
    prompt = carregar_prompt()
    for trecho in (
        "mecanismo_alvo",
        "gabarito_alvo",
        "trecho_que_decide",
        "validador",
        "independente",
    ):
        assert trecho in prompt
    assert re.findall(r"\{[a-z_]+\}", prompt) == []


def test_mensagem_lista_fontes_originais_mecanismo_e_gabarito() -> None:
    mensagem = montar_mensagem(ENTRADA)
    assert "F1 | Lei 8.429/1992 art. 1 |" in mensagem
    assert "Os atos de improbidade são punidos na forma da lei." in mensagem
    assert "mecanismo_alvo: troca_de_verbo" in mensagem
    assert "gabarito_alvo: E" in mensagem


def test_mensagem_sem_originais_nao_quebra() -> None:
    entrada = ENTRADA.model_copy(update={"originais": []})
    mensagem = montar_mensagem(entrada)
    assert "F1 | Lei 8.429/1992 art. 1 |" in mensagem


def test_interpretar_resposta() -> None:
    resultado = interpretar_resposta(JSON_RESPOSTA)
    assert isinstance(resultado, QuestaoGerada)
    assert resultado.gabarito == "E"
    assert resultado.publicado is False
    # tolera cerca de código, como os outros agentes
    resultado_cercado = interpretar_resposta(f"```json\n{JSON_RESPOSTA}\n```")
    assert isinstance(resultado_cercado, QuestaoGerada)


def test_interpretar_resposta_invalida_levanta() -> None:
    with pytest.raises(ValidationError):
        interpretar_resposta("{}")


def test_criar_gerador_adk_exige_chave(config_teste: Configuracoes) -> None:
    with pytest.raises(ValueError, match="GOOGLE_API_KEY ausente"):
        criar_gerador_adk(config_teste, lambda chamada: None)


def test_criar_gerador_adk_com_chave_nao_faz_rede(config_teste: Configuracoes) -> None:
    config = config_teste.model_copy(update={"google_api_key": SecretStr("chave-falsa")})
    gerador = criar_gerador_adk(config, lambda chamada: None)
    assert isinstance(gerador, GeradorDeQuestao)


def test_criar_gerador_adk_usa_json_mode_sem_output_schema(config_teste: Configuracoes) -> None:
    from google.adk.agents import LlmAgent

    config = config_teste.model_copy(update={"google_api_key": SecretStr("chave-falsa")})
    agente = criar_gerador_adk(config, lambda chamada: None).agente
    assert isinstance(agente, LlmAgent)
    assert agente.output_schema is None
    assert agente.generate_content_config is not None
    assert agente.generate_content_config.response_mime_type == "application/json"
    assert agente.include_contents == "none"
