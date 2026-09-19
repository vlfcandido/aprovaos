# O que é: testes do agente `gerador-de-justificativa` — porta, prompt em arquivo, mensagem com
# a questão e os dispositivos ligados, `interpretar_resposta` para os dois `tipo_item`, e a
# fábrica do ADK sem chave (mesmo padrão de `test_analista_de_edital.py`). Quando ler: ao mudar
# o prompt ou o contrato de entrada/saída do agente.
import re

import pytest
from pydantic import SecretStr, ValidationError

from aprovaos.agentes.gerador_de_justificativa import (
    GeradorDeJustificativa,
    carregar_prompt,
    criar_gerador_adk,
    interpretar_resposta,
    montar_mensagem,
)
from aprovaos.config import Configuracoes
from aprovaos.dominio.justificativa import (
    AlternativaParaJustificar,
    DispositivoParaJustificar,
    JustificativaCertoErrado,
    JustificativaMultiplaEscolha,
    QuestaoParaJustificar,
)

DISPOSITIVO = DispositivoParaJustificar(
    citacao_canonica="Lei 8.429/1992 art. 1º",
    texto="Art. 1º Os atos de improbidade administrativa [...] serão punidos na forma desta lei.",
)

QUESTAO_CE = QuestaoParaJustificar(
    tipo_item="certo_errado",
    comando="Julgue o item a seguir.",
    texto_apoio=None,
    enunciado="Os atos de improbidade administrativa não se sujeitam a punição.",
    gabarito="E",
    alternativas=None,
    dispositivos=[DISPOSITIVO],
)

QUESTAO_ME = QuestaoParaJustificar(
    tipo_item="multipla_escolha",
    comando="Assinale a alternativa correta.",
    texto_apoio=None,
    enunciado="Sobre a Lei nº 8.429/1992, é correto afirmar que:",
    gabarito=None,
    alternativas=[
        AlternativaParaJustificar(
            letra=letra, texto=f"texto da alternativa {letra}", correta=letra == "A"
        )
        for letra in "ABCDE"
    ],
    dispositivos=[DISPOSITIVO],
)

JSON_CE = """
{
  "afirmacoes_certo": [
    {"texto": "Se dissesse que há punição, estaria certo",
     "dispositivo": "Lei 8.429/1992 art. 1º", "trecho_que_decide": "serão punidos"}
  ],
  "afirmacoes_errado": [
    {"texto": "A lei prevê punição, então o item está errado",
     "dispositivo": "Lei 8.429/1992 art. 1º", "trecho_que_decide": "serão punidos"}
  ]
}
"""

JSON_ME = """
{
  "alternativas": [
    {"letra": "A", "afirmacoes": [{"texto": "é a correta",
      "dispositivo": "Lei 8.429/1992 art. 1º", "trecho_que_decide": "serão punidos"}]},
    {"letra": "B", "afirmacoes": [{"texto": "não é",
      "dispositivo": "Lei 8.429/1992 art. 1º", "trecho_que_decide": "serão punidos"}]},
    {"letra": "C", "afirmacoes": [{"texto": "não é",
      "dispositivo": "Lei 8.429/1992 art. 1º", "trecho_que_decide": "serão punidos"}]},
    {"letra": "D", "afirmacoes": [{"texto": "não é",
      "dispositivo": "Lei 8.429/1992 art. 1º", "trecho_que_decide": "serão punidos"}]},
    {"letra": "E", "afirmacoes": [{"texto": "não é",
      "dispositivo": "Lei 8.429/1992 art. 1º", "trecho_que_decide": "serão punidos"}]}
  ]
}
"""


class GeradorFalso:
    """Dublê da porta: devolve sempre o objeto recebido no construtor."""

    def __init__(self, resposta: JustificativaCertoErrado | JustificativaMultiplaEscolha) -> None:
        self.resposta = resposta
        self.chamadas = 0

    async def gerar(
        self, questao: QuestaoParaJustificar
    ) -> JustificativaCertoErrado | JustificativaMultiplaEscolha:
        self.chamadas += 1
        return self.resposta


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_gerador_falso_e_uma_implementacao_da_porta() -> None:
    falso = GeradorFalso(JustificativaCertoErrado(afirmacoes_certo=[], afirmacoes_errado=[]))
    assert isinstance(falso, GeradorDeJustificativa)
    resposta = await falso.gerar(QUESTAO_CE)
    assert falso.chamadas == 1
    assert isinstance(resposta, JustificativaCertoErrado)


def test_prompt_existe_e_fala_do_contrato() -> None:
    prompt = carregar_prompt()
    for trecho in (
        "trecho_que_decide",
        "afirmacoes_certo",
        "afirmacoes_errado",
        "alternativas",
        "não pode citar dispositivo",
    ):
        assert trecho in prompt
    assert re.findall(r"\{[a-z_]+\}", prompt) == []


def test_mensagem_certo_errado_lista_a_questao_e_os_dispositivos() -> None:
    mensagem = montar_mensagem(QUESTAO_CE)
    assert "certo_errado" in mensagem
    assert QUESTAO_CE.enunciado in mensagem
    assert DISPOSITIVO.citacao_canonica in mensagem
    assert DISPOSITIVO.texto in mensagem
    assert "gabarito: E" in mensagem


def test_mensagem_multipla_escolha_lista_as_alternativas() -> None:
    mensagem = montar_mensagem(QUESTAO_ME)
    assert "multipla_escolha" in mensagem
    for letra in "ABCDE":
        assert f"{letra} | " in mensagem
    assert "correta: A" in mensagem


def test_interpretar_resposta_certo_errado() -> None:
    resultado = interpretar_resposta(JSON_CE, "certo_errado")
    assert isinstance(resultado, JustificativaCertoErrado)
    assert len(resultado.afirmacoes_certo) == 1
    assert len(resultado.afirmacoes_errado) == 1
    # tolera cerca de código, como os outros agentes
    resultado_cercado = interpretar_resposta(f"```json\n{JSON_CE}\n```", "certo_errado")
    assert isinstance(resultado_cercado, JustificativaCertoErrado)


def test_interpretar_resposta_multipla_escolha() -> None:
    resultado = interpretar_resposta(JSON_ME, "multipla_escolha")
    assert isinstance(resultado, JustificativaMultiplaEscolha)
    assert len(resultado.alternativas) == 5


def test_interpretar_resposta_tipo_item_desconhecido() -> None:
    with pytest.raises(ValueError, match="tipo_item"):
        interpretar_resposta(JSON_CE, "dissertativa")


def test_interpretar_resposta_invalida_levanta() -> None:
    with pytest.raises(ValidationError):
        interpretar_resposta("{}", "certo_errado")


def test_criar_gerador_adk_exige_chave(config_teste: Configuracoes) -> None:
    with pytest.raises(ValueError, match="GOOGLE_API_KEY ausente"):
        criar_gerador_adk(config_teste, lambda chamada: None)


def test_criar_gerador_adk_com_chave_nao_faz_rede(config_teste: Configuracoes) -> None:
    config = config_teste.model_copy(update={"google_api_key": SecretStr("chave-falsa")})
    gerador = criar_gerador_adk(config, lambda chamada: None)
    assert isinstance(gerador, GeradorDeJustificativa)


def test_criar_gerador_adk_usa_json_mode_sem_output_schema(config_teste: Configuracoes) -> None:
    from google.adk.agents import LlmAgent

    config = config_teste.model_copy(update={"google_api_key": SecretStr("chave-falsa")})
    agente = criar_gerador_adk(config, lambda chamada: None).agente
    assert isinstance(agente, LlmAgent)
    assert agente.output_schema is None
    assert agente.generate_content_config is not None
    assert agente.generate_content_config.response_mime_type == "application/json"
    assert agente.include_contents == "none"
