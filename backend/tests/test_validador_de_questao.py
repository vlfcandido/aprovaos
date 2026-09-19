# O que é: testes do agente `validador-de-questao` (fatia 5) — porta, prompt em arquivo,
# mensagem com o item **sem gabarito** e o dossiê, `interpretar_resposta` e a fábrica do ADK sem
# chave (mesmo padrão de `test_gerador_de_aula.py`). Quando ler: ao mudar o prompt ou o contrato
# de entrada/saída do agente.
import re

import pytest
from pydantic import SecretStr, ValidationError

from aprovaos.agentes.validador_de_questao import (
    ValidadorDeQuestao,
    carregar_prompt,
    criar_validador_adk,
    interpretar_resposta,
    montar_mensagem,
)
from aprovaos.config import Configuracoes
from aprovaos.dominio.dossie import FonteDossie
from aprovaos.dominio.validacao_questao import EntradaValidadorQuestao, ResolucaoValidador

FONTE = FonteDossie(
    id="F1",
    tipo="norma",
    norma="lei-8429-1992",
    artigo="1",
    citacao_canonica="Lei 8.429/1992 art. 1",
    url="https://planalto.gov.br/lei-8429",
    trecho="Art. 1º Os atos de improbidade administrativa serão punidos na forma desta lei.",
)

ENTRADA = EntradaValidadorQuestao(
    tipo_item="certo_errado",
    comando="Acerca da improbidade administrativa, julgue o item a seguir.",
    enunciado="Os atos de improbidade administrativa serão perdoados na forma desta lei.",
    alternativas=None,
    fontes=[FONTE],
)

JSON_RESPOSTA = '{"gabarito": "E"}'


class ValidadorFalso:
    """Dublê da porta: devolve sempre o objeto recebido no construtor."""

    def __init__(self, resposta: ResolucaoValidador) -> None:
        self.resposta = resposta
        self.chamadas = 0

    async def resolver(self, entrada: EntradaValidadorQuestao) -> ResolucaoValidador:
        self.chamadas += 1
        return self.resposta


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_validador_falso_e_uma_implementacao_da_porta() -> None:
    resposta = interpretar_resposta(JSON_RESPOSTA)
    falso = ValidadorFalso(resposta)
    assert isinstance(falso, ValidadorDeQuestao)
    devolvido = await falso.resolver(ENTRADA)
    assert falso.chamadas == 1
    assert devolvido is resposta


def test_prompt_existe_e_fala_do_contrato() -> None:
    prompt = carregar_prompt()
    for trecho in ("gabarito", "independente", "nunca recebe o gabarito"):
        assert trecho in prompt
    assert re.findall(r"\{[a-z_]+\}", prompt) == []


def test_mensagem_nao_vaza_gabarito_nem_trecho_que_decide() -> None:
    mensagem = montar_mensagem(ENTRADA)
    assert "F1 | Lei 8.429/1992 art. 1 |" in mensagem
    assert "gabarito_alvo" not in mensagem
    assert "trecho_que_decide" not in mensagem


def test_mensagem_com_alternativas() -> None:
    from aprovaos.dominio.validacao_questao import AlternativaParaValidador

    entrada = ENTRADA.model_copy(
        update={
            "tipo_item": "multipla_escolha",
            "alternativas": [
                AlternativaParaValidador(letra=letra, texto=f"Texto {letra}") for letra in "ABCDE"
            ],
        }
    )
    mensagem = montar_mensagem(entrada)
    assert "A | Texto A" in mensagem
    assert "E | Texto E" in mensagem


def test_interpretar_resposta() -> None:
    resultado = interpretar_resposta(JSON_RESPOSTA)
    assert isinstance(resultado, ResolucaoValidador)
    assert resultado.gabarito == "E"
    resultado_cercado = interpretar_resposta(f"```json\n{JSON_RESPOSTA}\n```")
    assert isinstance(resultado_cercado, ResolucaoValidador)


def test_interpretar_resposta_invalida_levanta() -> None:
    with pytest.raises(ValidationError):
        interpretar_resposta("{}")


def test_criar_validador_adk_exige_chave(config_teste: Configuracoes) -> None:
    with pytest.raises(ValueError, match="GOOGLE_API_KEY ausente"):
        criar_validador_adk(config_teste, lambda chamada: None)


def test_criar_validador_adk_com_chave_nao_faz_rede(config_teste: Configuracoes) -> None:
    config = config_teste.model_copy(update={"google_api_key": SecretStr("chave-falsa")})
    validador = criar_validador_adk(config, lambda chamada: None)
    assert isinstance(validador, ValidadorDeQuestao)


def test_criar_validador_adk_usa_json_mode_sem_output_schema(config_teste: Configuracoes) -> None:
    from google.adk.agents import LlmAgent

    config = config_teste.model_copy(update={"google_api_key": SecretStr("chave-falsa")})
    agente = criar_validador_adk(config, lambda chamada: None).agente
    assert isinstance(agente, LlmAgent)
    assert agente.output_schema is None
    assert agente.generate_content_config is not None
    assert agente.generate_content_config.response_mime_type == "application/json"
    assert agente.include_contents == "none"
