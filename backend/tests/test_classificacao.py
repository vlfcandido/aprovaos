# O que é: testes do passo 8 da V3 — o léxico por regras (`classificar_por_regras`), o lote
# (`montar_lotes`), a interpretação da resposta da IA (`interpretar_resposta`, entrada a entrada)
# e a orquestração `classificar` (fatia por `tamanho_lote`, IA → cada item confere → regras,
# nunca bloqueia), além de `escolher_classificador` (sem chave → regras). Quando ler: ao ajustar
# o léxico para um edital real que ele não cobre, ou ao mudar o fluxo de fallback da
# classificação.
import json
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import SecretStr
from sqlalchemy.orm import Session

from aprovaos.agentes.classificador import (
    _TENTATIVAS_MAX,
    MOTIVO_SEM_CHAVE,
    ClassificadorAdk,
    LimiteDeTaxaExcedido,
    RespostaDoModeloAusente,
    _com_retentativa_de_limite,
    _segundos_de_retentativa,
    criar_classificador_adk,
    escolher_classificador,
)
from aprovaos.config import Configuracoes
from aprovaos.dados.modelos import Tenant, Usuario
from aprovaos.dominio.edital import extrair_conteudo_programatico
from aprovaos.dominio.pdf import extrair_texto
from aprovaos.dominio.prova import ItemBruto, segmentar_cebraspe
from aprovaos.motor.curadoria.classificacao import (
    SEM_CORRESPONDENCIA,
    Classificacao,
    ClassificacaoInvalida,
    ClassificadorDeTopico,
    ItemParaClassificar,
    MotivosRejeicao,
    TopicoVocabulario,
    classificar,
    classificar_por_regras,
    interpretar_resposta,
    montar_lotes,
)

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_MD = RAIZ / "docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md"
FIXTURE_PROVA = (
    RAIZ
    / "knowledge/provas/TJ_PA_25_SERVIDOR"
    / "C15F414E0E91EF109220A73BDF53B232C4466F64770A91E715C56DCB94131F41.pdf"
)

# Tamanho de lote alto o bastante para não fatiar os casos pequenos destes testes — quem testa
# a fatia em si é `test_classificar_fatia_pelo_tamanho_do_lote`.
_TAMANHO_LOTE_GRANDE = 100


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def vocabulario() -> list[TopicoVocabulario]:
    """O vocabulário do fixture de edital (fictício, Fase 4; 36 tópicos, 22 de Direito)."""
    texto = FIXTURE_MD.read_text(encoding="utf-8")
    materias = extrair_conteudo_programatico(texto)
    return [
        TopicoVocabulario(
            slug=topico.slug, materia=materia.slug, texto_original=topico.texto_original
        )
        for materia in materias
        for topico in materia.topicos
    ]


@pytest.fixture(scope="module")
def itens_reais_por_numero() -> dict[int, ItemBruto]:
    """Os 70 itens reais do caderno de Direito da TJ-PA, indexados por `numero_item`."""
    texto = extrair_texto(FIXTURE_PROVA.read_bytes())
    return {item.numero_item: item for item in segmentar_cebraspe(texto)}


def _item_para_classificar(
    numero: int, itens_reais_por_numero: dict[int, ItemBruto]
) -> ItemParaClassificar:
    bruto = itens_reais_por_numero[numero]
    return ItemParaClassificar(
        numero_item=bruto.numero_item, comando=bruto.comando, enunciado=bruto.enunciado
    )


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


# --- Ruling 21 (rodada 1 de correção): palavra isolada não basta para "media" ------------


@pytest.mark.parametrize("numero", [52, 67, 68, 69, 70, 89, 90, 91, 92])
def test_regras_palavra_isolada_nao_basta_fica_baixa(
    numero: int,
    vocabulario: list[TopicoVocabulario],
    itens_reais_por_numero: dict[int, ItemBruto],
) -> None:
    """Casos reais confirmados pela auditoria: só uma palavra genérica casou, isso não basta.

    Item 52 ("jurídicas"), 67–69 ("constituição"), 70 ("competência") e 89–92 ("direitos") são
    falsos positivos que a rodada 1 de revisão encontrou no PDF real — o termo bate com um
    tópico errado só porque a palavra aparece solta no comando (compartilhado por todo o bloco)
    ou no enunciado, sem que o item seja realmente sobre aquele tópico.
    """
    item = _item_para_classificar(numero, itens_reais_por_numero)

    resultado = classificar_por_regras([item], vocabulario)

    assert resultado[0].topico_slug is None
    assert resultado[0].confianca == "baixa"
    assert "não basta" in resultado[0].evidencia


def test_regras_lei_citada_no_item_real_continua_alta(
    vocabulario: list[TopicoVocabulario], itens_reais_por_numero: dict[int, ItemBruto]
) -> None:
    """Item 59 (real): cita a Lei nº 8.429/1992 — continua `alta`, a correção não mexeu aqui."""
    item = _item_para_classificar(59, itens_reais_por_numero)

    resultado = classificar_por_regras([item], vocabulario)

    assert resultado[0].topico_slug == "dir-adm-06-improbidade-administrativa"
    assert resultado[0].confianca == "alta"


def test_regras_frase_de_duas_palavras_no_item_real_continua_media(
    vocabulario: list[TopicoVocabulario], itens_reais_por_numero: dict[int, ItemBruto]
) -> None:
    """Item 60 (real): "atos administrativos" é frase de 2+ palavras — continua `media`."""
    item = _item_para_classificar(60, itens_reais_por_numero)

    resultado = classificar_por_regras([item], vocabulario)

    assert resultado[0].topico_slug == "dir-adm-02-atos-administrativos"
    assert resultado[0].confianca == "media"


def test_lote_respeita_tamanho() -> None:
    assert montar_lotes(itens=45, tamanho=20) == [20, 20, 5]


def test_interpretar_resposta_do_lote(vocabulario: list[TopicoVocabulario]) -> None:
    slugs_validos = {topico.slug for topico in vocabulario}
    texto = (
        '[{"numero_item": 58, "topico_slug": "dir-adm-04-licitacoes-contratos", '
        '"confianca": "alta", "evidencia": "cita a Lei nº 14.133/2021"}]'
    )

    classificacoes, motivos_rejeicao = interpretar_resposta(texto, slugs_validos)

    assert classificacoes == [
        Classificacao(
            numero_item=58,
            topico_slug="dir-adm-04-licitacoes-contratos",
            confianca="alta",
            evidencia="cita a Lei nº 14.133/2021",
            origem="ia",
        )
    ]
    assert motivos_rejeicao == {}


def test_interpretar_resposta_slug_invalido_e_rejeitada_sem_derrubar_as_boas(
    vocabulario: list[TopicoVocabulario],
) -> None:
    """Correção crítica da rodada 1: 1 entrada ruim não derruba as outras do mesmo lote."""
    slugs_validos = {topico.slug for topico in vocabulario}
    texto = json.dumps(
        [
            {
                "numero_item": 1,
                "topico_slug": "dir-adm-04-licitacoes-contratos",
                "confianca": "alta",
                "evidencia": "cita a Lei nº 14.133/2021",
            },
            {
                "numero_item": 2,
                "topico_slug": "topico-que-nao-existe",
                "confianca": "alta",
                "evidencia": "...",
            },
        ]
    )

    classificacoes, motivos_rejeicao = interpretar_resposta(texto, slugs_validos)

    assert [c.numero_item for c in classificacoes] == [1]
    assert 2 in motivos_rejeicao
    assert "topico-que-nao-existe" in motivos_rejeicao[2]


def test_interpretar_resposta_json_invalido_levanta_erro(
    vocabulario: list[TopicoVocabulario],
) -> None:
    slugs_validos = {topico.slug for topico in vocabulario}

    with pytest.raises(ClassificacaoInvalida):
        interpretar_resposta("isto não é JSON", slugs_validos)


def test_interpretar_resposta_que_nao_e_lista_levanta_erro(
    vocabulario: list[TopicoVocabulario],
) -> None:
    slugs_validos = {topico.slug for topico in vocabulario}

    with pytest.raises(ClassificacaoInvalida):
        interpretar_resposta('{"numero_item": 1}', slugs_validos)


class _ClassificadorFalso:
    """Dublê da porta: devolve sempre a resposta dada no construtor."""

    def __init__(
        self, resposta: list[Classificacao], motivos_rejeicao: MotivosRejeicao | None = None
    ) -> None:
        self.resposta = resposta
        self.motivos_rejeicao = motivos_rejeicao or {}

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]
    ) -> tuple[list[Classificacao], MotivosRejeicao]:
        return self.resposta, self.motivos_rejeicao


class _ClassificadorQueLevanta:
    """Dublê da porta: sempre levanta (simula falha do provedor)."""

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]
    ) -> tuple[list[Classificacao], MotivosRejeicao]:
        raise RuntimeError("provedor fora do ar")


class _ClassificadorComRespostaBruta:
    """Dublê que interpreta uma resposta crua de IA, como o `ClassificadorAdk` real faria."""

    def __init__(self, texto: str) -> None:
        self._texto = texto

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]
    ) -> tuple[list[Classificacao], MotivosRejeicao]:
        slugs_validos = {topico.slug for topico in vocabulario}
        return interpretar_resposta(self._texto, slugs_validos)


class _ClassificadorQueRegistraChamadas:
    """Dublê que registra o tamanho de cada chamada e devolve "baixa" para todo item recebido."""

    def __init__(self) -> None:
        self.tamanhos_chamados: list[int] = []

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]
    ) -> tuple[list[Classificacao], MotivosRejeicao]:
        self.tamanhos_chamados.append(len(itens))
        classificacoes = [
            Classificacao(
                numero_item=item.numero_item,
                topico_slug=None,
                confianca="baixa",
                evidencia="dublê",
                origem="ia",
            )
            for item in itens
        ]
        return classificacoes, {}


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

    resultado = await classificar(
        itens, vocabulario, _ClassificadorFalso(resposta_ia), None, _TAMANHO_LOTE_GRANDE
    )

    assert resultado.classificacoes[0].origem == "ia"
    assert resultado.classificacoes[0].motivo_fallback is None
    assert resultado.classificacoes[1].origem == "regras"
    assert resultado.classificacoes[1].motivo_fallback == "item ausente na resposta do modelo"


@pytest.mark.anyio
async def test_slug_inventado_cai_para_regras_so_naquele_item(
    vocabulario: list[TopicoVocabulario],
) -> None:
    """Correção crítica da rodada 1: N−1 entradas boas + 1 slug inventado → só 1 vai para regras."""
    itens = [
        ItemParaClassificar(numero_item=1, comando=None, enunciado="Enunciado 1 qualquer."),
        ItemParaClassificar(numero_item=2, comando=None, enunciado="Enunciado 2 qualquer."),
        ItemParaClassificar(numero_item=3, comando=None, enunciado="Enunciado 3 qualquer."),
    ]
    resposta = json.dumps(
        [
            {
                "numero_item": 1,
                "topico_slug": "dir-adm-02-atos-administrativos",
                "confianca": "media",
                "evidencia": "...",
            },
            {
                "numero_item": 2,
                "topico_slug": "dir-adm-02-atos-administrativos",
                "confianca": "media",
                "evidencia": "...",
            },
            {
                "numero_item": 3,
                "topico_slug": "topico-que-nao-existe",
                "confianca": "alta",
                "evidencia": "...",
            },
        ]
    )

    resultado = await classificar(
        itens, vocabulario, _ClassificadorComRespostaBruta(resposta), None, _TAMANHO_LOTE_GRANDE
    )

    assert resultado.classificacoes[0].origem == "ia"
    assert resultado.classificacoes[1].origem == "ia"
    assert resultado.classificacoes[2].origem == "regras"
    assert resultado.classificacoes[2].motivo_fallback is not None
    assert "topico-que-nao-existe" in resultado.classificacoes[2].motivo_fallback


@pytest.mark.anyio
async def test_fallback_por_erro_da_ia(vocabulario: list[TopicoVocabulario]) -> None:
    itens = [ItemParaClassificar(numero_item=1, comando=None, enunciado="Enunciado qualquer.")]

    resultado = await classificar(
        itens, vocabulario, _ClassificadorQueLevanta(), None, _TAMANHO_LOTE_GRANDE
    )

    assert resultado.classificacoes[0].origem == "regras"
    assert resultado.classificacoes[0].motivo_fallback == "erro na IA: RuntimeError"


@pytest.mark.anyio
async def test_sem_classificador_ia_usa_regras_com_motivo(
    vocabulario: list[TopicoVocabulario],
) -> None:
    itens = [ItemParaClassificar(numero_item=1, comando=None, enunciado="Enunciado qualquer.")]

    resultado = await classificar(
        itens, vocabulario, None, "sem GOOGLE_API_KEY", _TAMANHO_LOTE_GRANDE
    )

    assert resultado.classificacoes[0].origem == "regras"
    assert resultado.classificacoes[0].motivo_fallback == "sem GOOGLE_API_KEY"


@pytest.mark.anyio
async def test_classificar_fatia_pelo_tamanho_do_lote(vocabulario: list[TopicoVocabulario]) -> None:
    """Correção importante da rodada 1: `classificar` usa `montar_lotes`, não manda tudo de vez."""
    itens = [
        ItemParaClassificar(numero_item=numero, comando=None, enunciado=f"Item {numero}.")
        for numero in range(1, 46)
    ]
    dublê = _ClassificadorQueRegistraChamadas()

    resultado = await classificar(itens, vocabulario, dublê, None, tamanho_lote=20)

    assert dublê.tamanhos_chamados == [20, 20, 5]
    assert [c.numero_item for c in resultado.classificacoes] == list(range(1, 46))
    assert len(resultado.classificacoes) == 45


def test_sem_chave_vai_para_regras(db: Session, config_teste: Configuracoes) -> None:
    tenant = Tenant(tipo="pf", nome="Linda")
    usuario = Usuario(email="linda@exemplo.com", senha_hash="h", tenant=tenant)
    db.add(usuario)
    db.commit()

    classificador, motivo = escolher_classificador(db, config_teste, usuario)

    assert classificador is None
    assert motivo == MOTIVO_SEM_CHAVE


class _ErroDeLimite(Exception):
    """Dublê do `google.genai.errors.ClientError` de 429 — só o que a retentativa usa.

    O formato de `details` é o real, medido contra a API (passo 12b): `error.details` é uma
    lista de objetos tipados, um deles com `@type` terminando em `RetryInfo` e `retryDelay`
    como string de segundos (`"22s"`).
    """

    def __init__(self, retry_delay: str | None) -> None:
        self.code = 429
        detalhes_retry = (
            [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay}]
            if retry_delay
            else []
        )
        self.details = {"error": {"code": 429, "details": detalhes_retry}}
        super().__init__("429 RESOURCE_EXHAUSTED")


@pytest.mark.anyio
async def test_retentativa_espera_o_retry_delay_e_tenta_de_novo() -> None:
    """429 uma vez, com `retryDelay`, depois sucesso: 1 retentativa, resultado da 2ª chamada."""
    chamadas = 0

    async def operacao() -> str:
        nonlocal chamadas
        chamadas += 1
        if chamadas == 1:
            raise _ErroDeLimite("0.01s")
        return "resposta-boa"

    resultado = await _com_retentativa_de_limite(operacao)

    assert resultado == "resposta-boa"
    assert chamadas == 2


@pytest.mark.anyio
async def test_retentativa_desiste_quando_a_espera_sugerida_e_maior_que_o_teto() -> None:
    """`retryDelay` gigante (cota diária, não por minuto) → desiste na hora, sem dormir."""

    async def operacao() -> str:
        raise _ErroDeLimite("3600s")

    with pytest.raises(_ErroDeLimite):
        await _com_retentativa_de_limite(operacao)


@pytest.mark.anyio
async def test_retentativa_esgota_tentativas_e_relanca_o_ultimo_erro() -> None:
    """429 sempre, sem nunca ter sucesso: relança depois de `_TENTATIVAS_MAX` tentativas."""
    chamadas = 0

    async def operacao() -> str:
        nonlocal chamadas
        chamadas += 1
        raise _ErroDeLimite("0.01s")

    with pytest.raises(_ErroDeLimite):
        await _com_retentativa_de_limite(operacao)

    assert chamadas == _TENTATIVAS_MAX


@pytest.mark.anyio
async def test_retentativa_nao_intercepta_erro_que_nao_e_429() -> None:
    """Erro sem `code == 429` sobe na primeira tentativa, sem esperar nem tentar de novo."""
    chamadas = 0

    async def operacao() -> str:
        nonlocal chamadas
        chamadas += 1
        raise RuntimeError("erro qualquer, não é limite de taxa")

    with pytest.raises(RuntimeError):
        await _com_retentativa_de_limite(operacao)

    assert chamadas == 1


def test_criar_classificador_adk_nao_manda_thinking_config(config_teste: Configuracoes) -> None:
    """`gemini-3.5-flash-lite` rejeita `thinking_config` (passo 12c: achado real).

    O passo 12b tinha ligado `thinking_budget=0` para desligar o "pensamento" (medição do dono:
    568 tokens de pensamento por chamada de classificação, contra 96 de entrada e 102 de saída).
    Rodando de verdade contra `gemini-3.5-flash-lite` (o modelo do classificador a partir do
    passo 12c — cota diária é por modelo, achado do 12b), toda chamada voltou
    `400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': 'Request contains an invalid
    argument.', 'status': 'INVALID_ARGUMENT'}}` — sem `thinking_config` no `GenerateContentConfig`,
    a mesma chamada funcionou. `criar_classificador_adk` não manda mais esse campo; a pendência de
    medir `thinking_budget` (passo 12b, item 5) fica cancelada para este modelo, não só adiada.
    """
    from google.adk.agents import LlmAgent

    config = config_teste.model_copy(update={"google_api_key": SecretStr("chave-falsa")})
    agente = criar_classificador_adk(config, lambda chamada: None).agente

    assert isinstance(agente, LlmAgent)
    assert agente.generate_content_config is not None
    assert agente.generate_content_config.thinking_config is None


# --- Rodada 12b, achado da execução real: o ADK não deixa o 429 subir como exceção Python ----
#
# Medido rodando `curar --reclassificar` de verdade (com `GOOGLE_API_KEY` real, contra a cota do
# free tier já esgotada): o traço gravado tinha `erro="RespostaDoModeloAusente"`, não
# `_ResourceExhaustedError`, e a duração era < 1s — nenhuma retentativa real aconteceu.
# `google/adk/workflow/_node_runner.py` (`_execute_node`) captura a exceção do modelo e publica
# um `Event(error_code=getattr(erro, "status", None) or type(erro).__name__, ...)` — para um
# `ClientError` de 429, `.status` é a string `"RESOURCE_EXHAUSTED"` (vem de `response_json`, o
# mesmo JSON que carrega o `RetryInfo`). `_rodar` via só `evento.error_code`, então tratava
# QUALQUER erro do modelo como `RespostaDoModeloAusente` — sem `.code`, `_com_retentativa_de_limite`
# nunca reconhecia o 429. `LimiteDeTaxaExcedido` existe para fechar esse buraco.


def test_limite_de_taxa_excedido_extrai_retry_delay_da_mensagem_do_adk() -> None:
    """A mensagem real do ADK (`error_code: error_message`) ainda traz "Please retry in Ns.".

    O objeto `RetryInfo` estruturado não sobrevive à conversão do ADK de exceção para `Event`
    (só sobra o texto) — por isso a extração aqui é por regex na mensagem, não no `.details`
    completo que `google.genai.errors.ClientError` traria diretamente.
    """
    mensagem = (
        "RESOURCE_EXHAUSTED: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': "
        "'You exceeded your current quota... \\nPlease retry in 46.186756923s.', "
        "'status': 'RESOURCE_EXHAUSTED'}}"
    )

    erro = LimiteDeTaxaExcedido(mensagem)

    assert erro.code == 429
    assert _segundos_de_retentativa(erro) == pytest.approx(46.186756923)


def test_limite_de_taxa_excedido_sem_retry_delay_no_texto() -> None:
    """Mensagem sem "retry in Ns" reconhecível: `código` continua 429, mas sem espera sugerida
    (`_com_retentativa_de_limite` cai para `_ESPERA_PADRAO_S` nesse caso).
    """
    erro = LimiteDeTaxaExcedido("RESOURCE_EXHAUSTED: mensagem sem o texto de retentativa")

    assert erro.code == 429
    assert _segundos_de_retentativa(erro) is None


class _EventoFalso:
    """Dublê do `Event` do ADK — só os quatro campos/método que `_rodar` lê."""

    def __init__(
        self,
        *,
        final: bool,
        error_code: str | None = None,
        error_message: str | None = None,
        usage_metadata: object | None = None,
        content: object | None = None,
    ) -> None:
        self.error_code = error_code
        self.error_message = error_message
        self.usage_metadata = usage_metadata
        self.content = content
        self._final = final

    def is_final_response(self) -> bool:
        return self._final


class _RunnerFalso:
    """Dublê de `Runner`: `run_async` devolve os eventos dados, na ordem, sem rede."""

    def __init__(self, eventos: list[_EventoFalso]) -> None:
        self._eventos = eventos
        self.agent = None

    async def run_async(
        self, *, user_id: str, session_id: str, new_message: object
    ) -> AsyncIterator[_EventoFalso]:
        for evento in self._eventos:
            yield evento


class _ServicoSessaoFalso:
    """Dublê de `BaseSessionService`: `create_session` só devolve os ids recebidos."""

    async def create_session(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> SimpleNamespace:
        return SimpleNamespace(user_id=user_id, id=session_id)


def _classificador_com_eventos(eventos: list[_EventoFalso]) -> ClassificadorAdk:
    return ClassificadorAdk(
        runner=_RunnerFalso(eventos),  # type: ignore[arg-type]
        servico_sessao=_ServicoSessaoFalso(),  # type: ignore[arg-type]
        modelo="gemini-3.6-flash",
        registrar_chamada=lambda chamada: None,
        novo_conteudo=lambda texto: texto,  # type: ignore[arg-type,return-value]
    )


@pytest.mark.anyio
async def test_rodar_reconhece_resource_exhausted_como_limite_de_taxa() -> None:
    """`error_code == "RESOURCE_EXHAUSTED"` vira `LimiteDeTaxaExcedido` (`.code == 429`), não
    `RespostaDoModeloAusente` (sem `.code`) — é o que faz `_com_retentativa_de_limite` reconhecer
    e retentar em vez de desistir na primeira falha (achado da execução real, passo 12b).
    """
    evento = _EventoFalso(
        final=True,
        error_code="RESOURCE_EXHAUSTED",
        error_message="429 RESOURCE_EXHAUSTED. ... Please retry in 12.5s.",
    )
    classificador = _classificador_com_eventos([evento])

    with pytest.raises(LimiteDeTaxaExcedido) as excinfo:
        await classificador._rodar("mensagem")

    assert excinfo.value.code == 429
    assert _segundos_de_retentativa(excinfo.value) == pytest.approx(12.5)


@pytest.mark.anyio
async def test_rodar_outro_error_code_continua_resposta_ausente() -> None:
    """`error_code` que não é `RESOURCE_EXHAUSTED` continua virando `RespostaDoModeloAusente`
    (comportamento anterior, preservado) — não é todo erro do modelo que é limite de taxa.
    """
    evento = _EventoFalso(final=True, error_code="ValueError", error_message="schema inválido")
    classificador = _classificador_com_eventos([evento])

    with pytest.raises(RespostaDoModeloAusente):
        await classificador._rodar("mensagem")
