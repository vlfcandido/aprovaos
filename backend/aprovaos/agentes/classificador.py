"""Agente `classificador`: implementação ADK (Gemini) da porta `ClassificadorDeTopico`.

O que é: `ClassificadorAdk` + `criar_classificador_adk` — a única função que importa `google.*`,
e só quando chamada — e `escolher_classificador`, que decide se a IA entra (sem chave ou sem
teto → `None` com o motivo, mesmo padrão de `api.editais._escolher_analista`). O contrato
(`ClassificadorDeTopico`, `Classificacao`, `interpretar_resposta`, o fallback por regras) vive em
`aprovaos.motor.curadoria.classificacao`. `_com_retentativa_de_limite` (passo 12b da V3) é a
retentativa com espera para o erro 429 (limite de taxa) do free tier — genérica e testável sem
`google.*`: só olha `erro.code`/`erro.details`, o mesmo formato que
`google.genai.errors.ClientError` expõe. Quando ler: ao ligar a classificação num pipeline real,
ao mudar o prompt, ao investigar por que um lote saiu "por regras", ou ao mexer no limite de taxa.
"""

import asyncio
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy.orm import Session

from aprovaos.config import Configuracoes
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Usuario
from aprovaos.dados.repositorio_traco import registrar_traco
from aprovaos.motor.curadoria.classificacao import (
    Classificacao,
    ClassificadorDeTopico,
    ItemParaClassificar,
    MotivosRejeicao,
    TopicoVocabulario,
    interpretar_resposta,
)
from aprovaos.roteador.custo import (
    PRECOS_USD_POR_MILHAO,
    ChamadaLlm,
    ModeloSemPreco,
    estimar_custo_brl,
)
from aprovaos.roteador.teto import TetoDiario

if TYPE_CHECKING:  # só para anotações: nada de `google.*` em tempo de import
    from google.adk.runners import Runner
    from google.adk.sessions import BaseSessionService
    from google.adk.workflow._base_node import BaseNode
    from google.genai import types

NOME_AGENTE = "classificador"
APP_ADK = "aprovaos"
MOTIVO_SEM_CHAVE = "sem GOOGLE_API_KEY"
MOTIVO_TETO = "teto diário atingido"

# Free tier do AI Studio (medido no passo 12b, 18/09/2026): 5 requisições/min para
# `gemini-3.6-flash`. `_TENTATIVAS_MAX` cobre "pegou o minuto errado" sem virar laço infinito;
# `_ESPERA_MAXIMA_S` distingue isso de cota **diária** esgotada (a mensagem real trouxe
# `retryDelay` de dezenas de segundos para o limite por minuto — uma espera pedida na casa dos
# minutos/horas é outro problema, que esperar aqui só disfarçaria); `_ESPERA_PADRAO_S` só entra
# se a resposta trouxer `code == 429` sem o objeto `RetryInfo` (não observado até agora, mas o
# contrato de `ClientError` não garante que venha sempre).
_TENTATIVAS_MAX = 3
_ESPERA_PADRAO_S = 5.0
_ESPERA_MAXIMA_S = 90.0

# "Please retry in 46.186756923s." — texto que a API do Gemini sempre inclui na mensagem de um
# 429, visto tanto no `ClientError.details["error"]["message"]` cru quanto no
# `Event.error_message` que sobra depois do ADK converter a exceção (ver `LimiteDeTaxaExcedido`).
_MENSAGEM_RETRY_DELAY = re.compile(r"retry in ([\d.]+)s")


def _segundos_de_retentativa(erro: Exception) -> float | None:
    """Lê o `retryDelay` do `RetryInfo` de um erro 429, se ele vier na resposta.

    Formato real (`google.genai.errors.ClientError.details`, medido no passo 12b):
    `{"error": {..., "details": [{"@type": "…Help", …}, {"@type": "…RetryInfo", "retryDelay":
    "22s"}]}}`. Duck-typed de propósito — funciona com o erro real do SDK e com qualquer dublê
    de teste que só tenha o atributo `details` no mesmo formato.

    Args:
        erro: a exceção levantada pela chamada (só é chamada quando `erro.code == 429`).

    Returns:
        Os segundos sugeridos, ou `None` se a resposta não trouxer um `RetryInfo` reconhecível.
    """
    detalhes = getattr(erro, "details", None)
    if not isinstance(detalhes, dict):
        return None
    interno = detalhes.get("error")
    if not isinstance(interno, dict):
        return None
    for item in interno.get("details") or ():
        if not isinstance(item, dict) or not str(item.get("@type", "")).endswith("RetryInfo"):
            continue
        bruto = item.get("retryDelay")
        if isinstance(bruto, str) and bruto.endswith("s"):
            try:
                return float(bruto[:-1])
            except ValueError:
                return None
    return None


async def _com_retentativa_de_limite[T](operacao: Callable[[], Awaitable[T]]) -> T:
    """Roda `operacao`, retentando com espera quando ela levanta erro 429 (limite de taxa).

    Erro sem `code == 429` sobe na hora, sem espera — não é limite de taxa, é outra falha (a
    classificação já degrada para regras nesse caso, em `motor.curadoria.classificacao`). Um
    429 espera o `retryDelay` sugerido (ou `_ESPERA_PADRAO_S`, sem ele) e tenta de novo, até
    `_TENTATIVAS_MAX` vezes; uma espera sugerida maior que `_ESPERA_MAXIMA_S` não é tratada como
    "espere um pouco" — é cota diária esgotada, e bloquear a curadoria inteira por minutos/horas
    seria pior que deixar aquele lote cair para `ClassificadorPorRegras`.

    Args:
        operacao: a chamada a repetir (ex.: `lambda: self._rodar(mensagem)`).

    Returns:
        O que `operacao()` devolveu, na primeira tentativa que teve sucesso.

    Raises:
        Exception: a exceção da última tentativa — de um erro que não é 429, de `code == 429`
            esgotando as tentativas, ou de uma espera sugerida maior que `_ESPERA_MAXIMA_S`.
    """
    tentativa = 0
    while True:
        try:
            return await operacao()
        except Exception as erro:
            tentativa += 1
            if getattr(erro, "code", None) != 429 or tentativa >= _TENTATIVAS_MAX:
                raise
            espera = _segundos_de_retentativa(erro)
            if espera is None:
                espera = _ESPERA_PADRAO_S
            if espera > _ESPERA_MAXIMA_S:
                raise
            await asyncio.sleep(espera)


class LimiteDeTaxaExcedido(RuntimeError):
    """O provedor recusou a chamada por limite de taxa — 429/`RESOURCE_EXHAUSTED`.

    Achado da execução real do passo 12b: o ADK **não** deixa o `google.genai.errors.ClientError`
    de 429 subir como exceção Python até `Runner.run_async` — `_node_runner.py` (`_execute_node`)
    captura a exceção do modelo e publica um `Event(error_code=erro.status ou o nome da classe,
    error_message=str(erro))`; para um erro 429, `.status` é a string `"RESOURCE_EXHAUSTED"` (o
    mesmo `status` que vem no JSON da resposta, ao lado do `RetryInfo`). Sem esta classe, `_rodar`
    tratava isso como `RespostaDoModeloAusente` — sem `.code` — e `_com_retentativa_de_limite`
    nunca via um 429 para retentar; media aqui (`traco.duracao_ms < 1s` na rodada real) provou
    isso: nenhuma retentativa real acontecia, cada lote caía direto para
    `ClassificadorPorRegras` na primeira falha.

    O objeto `RetryInfo` estruturado não sobrevive à conversão do ADK para `Event` — só o texto
    da mensagem ("Please retry in 46.18s.") — por isso `.details` aqui é reconstruído por regex
    (`_MENSAGEM_RETRY_DELAY`) em vez de vir pronto do provedor; `_segundos_de_retentativa` lê os
    dois formatos (o de `ClientError.details` e este) sem saber a diferença.

    Attributes:
        code: sempre `429` — só existe uma razão para esta classe existir.
        details: o mesmo formato de `google.genai.errors.ClientError.details`, montado a partir
            do `retryDelay` encontrado no texto da mensagem (ou lista de `details` vazia, se a
            mensagem não trouxer um "retry in Ns" reconhecível).
    """

    def __init__(self, mensagem: str) -> None:
        """Guarda `code=429` e reconstrói `details` a partir do texto de `mensagem`."""
        self.code = 429
        encontrado = _MENSAGEM_RETRY_DELAY.search(mensagem)
        detalhes_retry = (
            [
                {
                    "@type": "type.googleapis.com/google.rpc.RetryInfo",
                    "retryDelay": f"{encontrado.group(1)}s",
                }
            ]
            if encontrado
            else []
        )
        self.details = {"error": {"code": 429, "details": detalhes_retry}}
        super().__init__(mensagem)


class RespostaDoModeloAusente(RuntimeError):
    """O ADK terminou sem resposta final com texto (ou `error_code` que não é limite de taxa)."""


def carregar_prompt() -> str:
    """Lê `prompts/classificador.md` do disco (chamado pela fábrica, nunca em import).

    Returns:
        O prompt estático (o vocabulário e os itens do lote vão na mensagem do usuário).
    """
    return (Path(__file__).parent / "prompts" / "classificador.md").read_text(encoding="utf-8")


def montar_mensagem(itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]) -> str:
    """Monta a mensagem do usuário: o vocabulário do edital e os itens do lote.

    Args:
        itens: os itens do lote a classificar.
        vocabulario: os tópicos do conteúdo programático do edital.

    Returns:
        Texto com as duas listas (`slug | materia | texto_original` e
        `numero_item | comando | enunciado`), para o modelo usar os slugs dados.
    """
    linhas_vocabulario = [
        f"{topico.slug} | {topico.materia} | {topico.texto_original}" for topico in vocabulario
    ]
    linhas_itens = [
        f"{item.numero_item} | {item.comando or ''} | {item.enunciado}" for item in itens
    ]
    return (
        "## Vocabulário de tópicos "
        f"({len(linhas_vocabulario)} linhas: slug | materia | texto_original)\n\n"
        + "\n".join(linhas_vocabulario)
        + f"\n\n## Itens do lote ({len(linhas_itens)} linhas: numero_item | comando | enunciado)"
        "\n\n" + "\n".join(linhas_itens) + "\n"
    )


class ClassificadorAdk:
    """Implementação da porta com `LlmAgent` + `Runner` do ADK.

    Nasce só em `criar_classificador_adk`. Cada `classificar_lote` abre uma sessão nova em
    memória, roda o agente uma vez, entrega ao callback uma `ChamadaLlm` (sucesso ou erro) e
    devolve as classificações interpretadas. O fallback item a item é de
    `aprovaos.motor.curadoria.classificacao.classificar`.
    """

    def __init__(
        self,
        runner: "Runner",
        servico_sessao: "BaseSessionService",
        modelo: str,
        registrar_chamada: Callable[[ChamadaLlm], None],
        novo_conteudo: Callable[[str], "types.Content"],
    ) -> None:
        """Guarda as dependências já construídas pela fábrica (sem I/O aqui)."""
        self._runner = runner
        self._servico_sessao = servico_sessao
        self._modelo = modelo
        self._registrar_chamada = registrar_chamada
        self._novo_conteudo = novo_conteudo

    @property
    def agente(self) -> "BaseNode":
        """O nó raiz do runner (o `LlmAgent` da fábrica; exposto para inspeção em teste)."""
        return self._runner.agent

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]
    ) -> tuple[list[Classificacao], MotivosRejeicao]:
        """Roda o agente uma vez sobre o lote e devolve as classificações interpretadas.

        Raises:
            RespostaDoModeloAusente: sem resposta final com texto.
            ClassificacaoInvalida: a resposta inteira não é aproveitável (não é JSON, ou não é
                uma lista) — uma entrada individual ruim não levanta, vem em
                `motivos_rejeicao`.
            Exception: qualquer falha do ADK/provedor (depois de esgotar a retentativa de 429,
                `_com_retentativa_de_limite`), relançada após o registro.
        """
        slugs_validos = {topico.slug for topico in vocabulario}
        mensagem = montar_mensagem(itens, vocabulario)
        iniciado_em = datetime.now(UTC)
        t0 = perf_counter()
        tokens_in: int | None = None
        tokens_out: int | None = None
        try:
            resposta, tokens_in, tokens_out = await _com_retentativa_de_limite(
                lambda: self._rodar(mensagem)
            )
        except Exception as erro:
            self._registrar_chamada(
                ChamadaLlm(
                    agente=NOME_AGENTE,
                    modelo=self._modelo,
                    iniciado_em=iniciado_em,
                    duracao_ms=int((perf_counter() - t0) * 1000),
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    custo_brl=self._custo(tokens_in, tokens_out),
                    resultado="erro",
                    erro=type(erro).__name__,
                )
            )
            raise
        self._registrar_chamada(
            ChamadaLlm(
                agente=NOME_AGENTE,
                modelo=self._modelo,
                iniciado_em=iniciado_em,
                duracao_ms=int((perf_counter() - t0) * 1000),
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                custo_brl=self._custo(tokens_in, tokens_out),
                resultado="ok",
            )
        )
        return interpretar_resposta(resposta, slugs_validos)

    async def _rodar(self, mensagem: str) -> tuple[str, int | None, int | None]:
        """Executa o runner numa sessão nova e devolve (texto final, tokens_in, tokens_out)."""
        sessao = await self._servico_sessao.create_session(
            app_name=APP_ADK, user_id="classificador", session_id=str(uuid4())
        )
        texto_final: str | None = None
        tokens_in: int | None = None
        tokens_out: int | None = None
        async for evento in self._runner.run_async(
            user_id=sessao.user_id,
            session_id=sessao.id,
            new_message=self._novo_conteudo(mensagem),
        ):
            if evento.usage_metadata is not None:
                tokens_in = evento.usage_metadata.prompt_token_count
                tokens_out = evento.usage_metadata.candidates_token_count
            if not evento.is_final_response():
                continue
            if evento.error_code:
                mensagem = f"{evento.error_code}: {evento.error_message}"
                if evento.error_code == "RESOURCE_EXHAUSTED":
                    raise LimiteDeTaxaExcedido(mensagem)
                raise RespostaDoModeloAusente(mensagem)
            if evento.content is not None and evento.content.parts:
                # Partes de "pensamento" (thought=True) não são a resposta.
                texto_final = "".join(
                    parte.text for parte in evento.content.parts if parte.text and not parte.thought
                )
        if not texto_final:
            raise RespostaDoModeloAusente("o agente terminou sem resposta final com texto")
        return texto_final, tokens_in, tokens_out

    def _custo(self, tokens_in: int | None, tokens_out: int | None) -> Decimal | None:
        """Custo estimado quando os dois contadores existem; senão `None`."""
        if tokens_in is None or tokens_out is None:
            return None
        return estimar_custo_brl(self._modelo, tokens_in, tokens_out)


def criar_classificador_adk(
    config: Configuracoes, registrar_chamada: Callable[[ChamadaLlm], None]
) -> ClassificadorAdk:
    """Fábrica do classificador real: importa o ADK, monta `LlmAgent` + `Runner` e devolve a porta.

    A chave vai por `genai.Client(api_key=…)` explícito, sem tocar `os.environ` (mesma decisão
    de `criar_analista_adk`). Sem `output_schema`: a resposta é pedida em JSON mode
    (`response_mime_type="application/json"`) com o esquema descrito no prompt, e
    `interpretar_resposta` é quem valida contra `Classificacao` e contra o vocabulário.

    Args:
        config: configurações com `google_api_key`, `modelo_classificacao`.
        registrar_chamada: recebe a `ChamadaLlm` de cada chamada (quem chama grava em `traco`).

    Returns:
        Um `ClassificadorAdk` pronto para `classificar_lote`.

    Raises:
        ValueError: sem `GOOGLE_API_KEY`.
        ModeloSemPreco: `modelo_classificacao` sem preço tabelado (o teto diário não saberia
            contar).
    """
    if config.google_api_key is None:
        raise ValueError("GOOGLE_API_KEY ausente")
    if config.modelo_classificacao not in PRECOS_USD_POR_MILHAO:
        raise ModeloSemPreco(config.modelo_classificacao)

    from google import genai
    from google.adk.agents import LlmAgent
    from google.adk.models.google_llm import Gemini
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    modelo = Gemini(
        model=config.modelo_classificacao,
        client=genai.Client(api_key=config.google_api_key.get_secret_value()),
    )
    agente = LlmAgent(
        name="classificador",
        model=modelo,
        instruction=carregar_prompt(),
        include_contents="none",
        # Sem `thinking_config`: o passo 12b tinha ligado `thinking_budget=0` para desligar o
        # "pensamento" (medição do dono: 568 tokens de pensamento contra 96 de entrada e 102 de
        # saída numa chamada de classificação). Rodando de verdade no passo 12c contra
        # `gemini-3.5-flash-lite` (o modelo do classificador a partir daqui — cota diária é por
        # modelo, achado do 12b), toda chamada com esse campo voltou `400 INVALID_ARGUMENT`; sem
        # ele, funcionou. A pendência de medir `thinking_budget` está cancelada para este modelo,
        # não só adiada — ver `docs/fatias/V3-execucao.md`.
        generate_content_config=types.GenerateContentConfig(
            response_mime_type="application/json", temperature=0.0
        ),
    )
    servico = InMemorySessionService()
    runner = Runner(agent=agente, app_name=APP_ADK, session_service=servico)

    def novo_conteudo(texto: str) -> types.Content:
        return types.Content(role="user", parts=[types.Part(text=texto)])

    return ClassificadorAdk(
        runner=runner,
        servico_sessao=servico,
        modelo=config.modelo_classificacao,
        registrar_chamada=registrar_chamada,
        novo_conteudo=novo_conteudo,
    )


def escolher_classificador(
    db: Session, config: Configuracoes, usuario: Usuario
) -> tuple[ClassificadorDeTopico | None, str | None]:
    """Decide se a IA entra: sem chave ou sem teto → `None` com o motivo; senão o classificador ADK.

    O callback entregue à fábrica grava cada `ChamadaLlm` em `traco` na sessão do request
    (mesmo padrão de `api.editais._escolher_analista`); o `commit` fica com quem chama.

    Args:
        db: sessão de banco (lê o gasto do dia para o teto).
        config: configurações (`google_api_key`, `teto_diario_brl`).
        usuario: o usuário cuja conta é debitada em `traco`.

    Returns:
        `(classificador, None)` quando a IA pode ser chamada; `(None, motivo)` quando não.
    """
    if config.google_api_key is None:
        return None, MOTIVO_SEM_CHAVE
    if not TetoDiario(config.teto_diario_brl).pode_chamar(db, agora_utc()):
        return None, MOTIVO_TETO

    def registrar(chamada: ChamadaLlm) -> None:
        registrar_traco(db, chamada, usuario_id=usuario.id)

    return criar_classificador_adk(config, registrar), None
