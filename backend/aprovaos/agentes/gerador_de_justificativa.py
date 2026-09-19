"""Agente `gerador-de-justificativa`: porta, ADK (Gemini) e interpretação da resposta.

O que é: `GeradorDeJustificativa` (porta assíncrona), `carregar_prompt`/`montar_mensagem`,
`interpretar_resposta` e `criar_gerador_adk` — a única função que importa `google.*`, e só
quando chamada. Mesmo padrão de `aprovaos.agentes.analista_de_edital` e
`aprovaos.agentes.classificador`: `LlmAgent` com JSON mode (sem `output_schema` — a razão é a
mesma da Q4/plano B do analista: o Developer API do Gemini rejeita o `additionalProperties` que
os `dict`/`Union` deste contrato viram em JSON Schema), `include_contents="none"`, prompt em
arquivo versionado.

**Não há implementação "por regras" desta porta** — ao contrário do `analista-de-edital` e do
`classificador`, escrever a justificativa de uma questão não é algo que um léxico determinístico
saiba fazer; o "nunca bloqueia" aqui é papel de quem chama (`aprovaos.motor.justificar`): uma
questão cuja geração falhar (rede, cota, resposta fora do contrato, validador mecânico
reprovando) simplesmente não recebe justificativa nesta rodada — resultado correto, não erro do
comando.

Quando ler: ao ligar o agente ao comando `motor.justificar`, ao mudar o prompt, ou ao investigar
por que uma justificativa saiu vazia/reprovada.
"""

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import uuid4

from aprovaos.config import Configuracoes
from aprovaos.dominio.justificativa import (
    JustificativaCertoErrado,
    JustificativaMultiplaEscolha,
    QuestaoParaJustificar,
)
from aprovaos.roteador.custo import (
    PRECOS_USD_POR_MILHAO,
    ChamadaLlm,
    ModeloSemPreco,
    estimar_custo_brl,
)

if TYPE_CHECKING:  # só para anotações: nada de `google.*` em tempo de import
    from google.adk.runners import Runner
    from google.adk.sessions import BaseSessionService
    from google.adk.workflow._base_node import BaseNode
    from google.genai import types

NOME_AGENTE = "gerador-de-justificativa"
APP_ADK = "aprovaos"
_CERCA_DE_CODIGO = re.compile(r"\A```[a-zA-Z]*\s*\n?(.*?)\n?```\Z", re.DOTALL)

RespostaJustificativa = JustificativaCertoErrado | JustificativaMultiplaEscolha


@runtime_checkable
class GeradorDeJustificativa(Protocol):
    """Porta do gerador: recebe a questão com os dispositivos ligados e devolve a justificativa."""

    async def gerar(self, questao: QuestaoParaJustificar) -> RespostaJustificativa:
        """Gera a justificativa (ainda não validada mecanicamente).

        Args:
            questao: comando/enunciado/alternativas/gabarito e os dispositivos já ligados à
                questão — a única fonte que o modelo pode citar.

        Returns:
            `JustificativaCertoErrado` quando `questao.tipo_item == "certo_errado"`;
            `JustificativaMultiplaEscolha` quando `"multipla_escolha"`.
        """
        ...


def carregar_prompt() -> str:
    """Lê `prompts/gerador-de-justificativa.md` do disco (chamado pela fábrica, nunca em import).

    Returns:
        O prompt estático (a questão e os dispositivos vão na mensagem do usuário).
    """
    return (Path(__file__).parent / "prompts" / "gerador-de-justificativa.md").read_text(
        encoding="utf-8"
    )


def montar_mensagem(questao: QuestaoParaJustificar) -> str:
    """Monta a mensagem do usuário: a questão, o gabarito/alternativas e os dispositivos ligados.

    Args:
        questao: a questão a justificar, com os dispositivos já ligados a ela.

    Returns:
        Texto com `tipo_item`, comando/texto de apoio/enunciado, gabarito ou alternativas, e a
        lista `citacao_canonica | texto` dos dispositivos — a única fonte permitida.
    """
    linhas = [f"tipo_item: {questao.tipo_item}"]
    if questao.comando:
        linhas.append(f"comando: {questao.comando}")
    if questao.texto_apoio:
        linhas.append(f"texto_apoio: {questao.texto_apoio}")
    linhas.append(f"enunciado: {questao.enunciado}")
    if questao.gabarito is not None:
        linhas.append(f"gabarito: {questao.gabarito}")
    if questao.alternativas is not None:
        linhas.append(
            f"## Alternativas ({len(questao.alternativas)} linhas: letra | texto | correta)"
        )
        for alternativa in questao.alternativas:
            marca = "correta: " + alternativa.letra if alternativa.correta else "distrator"
            linhas.append(f"{alternativa.letra} | {alternativa.texto} | {marca}")
    linhas.append(
        f"\n## Dispositivos ligados a esta questão ({len(questao.dispositivos)} linhas: "
        "citacao_canonica | texto)"
    )
    for dispositivo in questao.dispositivos:
        linhas.append(f"{dispositivo.citacao_canonica} | {dispositivo.texto}")
    return "\n".join(linhas) + "\n"


def interpretar_resposta(texto: str, tipo_item: str) -> RespostaJustificativa:
    """Converte a resposta do modelo no contrato certo para `tipo_item`, tolerando cerca de código.

    Args:
        texto: resposta bruta (JSON, possivelmente entre ```json … ```).
        tipo_item: `"certo_errado"` ou `"multipla_escolha"` — decide qual dos dois modelos
            Pydantic valida a resposta.

    Returns:
        `JustificativaCertoErrado` ou `JustificativaMultiplaEscolha`, conforme `tipo_item`.

    Raises:
        ValueError: `tipo_item` não é um dos dois valores conhecidos.
        pydantic.ValidationError: a resposta não cumpre o contrato esperado.
        json.JSONDecodeError: a resposta (depois de remover a cerca) não é JSON.
    """
    limpo = texto.strip()
    cercado = _CERCA_DE_CODIGO.match(limpo)
    if cercado is not None:
        limpo = cercado.group(1).strip()
    if tipo_item == "certo_errado":
        return JustificativaCertoErrado.model_validate(json.loads(limpo))
    if tipo_item == "multipla_escolha":
        return JustificativaMultiplaEscolha.model_validate(json.loads(limpo))
    raise ValueError(f"tipo_item desconhecido: {tipo_item!r}")


class RespostaDoModeloAusente(RuntimeError):
    """O ADK terminou sem resposta final com texto (ou com `error_code`)."""


class GeradorDeJustificativaAdk:
    """Implementação da porta com `LlmAgent` + `Runner` do ADK; nasce só em `criar_gerador_adk`.

    Cada `gerar` abre uma sessão nova em memória, roda o agente uma vez, entrega ao callback uma
    `ChamadaLlm` (sucesso ou erro) e devolve a justificativa interpretada — ainda **sem**
    validação mecânica; quem chama (`aprovaos.motor.justificar`) roda
    `verificar_justificativa_*` antes de gravar qualquer coisa.
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

    async def gerar(self, questao: QuestaoParaJustificar) -> RespostaJustificativa:
        """Roda o agente uma vez e devolve a justificativa interpretada.

        Raises:
            RespostaDoModeloAusente: sem resposta final com texto.
            pydantic.ValidationError: resposta fora do contrato.
            Exception: qualquer falha do ADK/provedor, relançada após o registro.
        """
        iniciado_em = datetime.now(UTC)
        t0 = perf_counter()
        tokens_in: int | None = None
        tokens_out: int | None = None
        try:
            resposta, tokens_in, tokens_out = await self._rodar(montar_mensagem(questao))
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
        return interpretar_resposta(resposta, questao.tipo_item)

    async def _rodar(self, mensagem: str) -> tuple[str, int | None, int | None]:
        """Executa o runner numa sessão nova e devolve (texto final, tokens_in, tokens_out)."""
        sessao = await self._servico_sessao.create_session(
            app_name=APP_ADK, user_id="gerador-de-justificativa", session_id=str(uuid4())
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
                raise RespostaDoModeloAusente(f"{evento.error_code}: {evento.error_message}")
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


def criar_gerador_adk(
    config: Configuracoes, registrar_chamada: Callable[[ChamadaLlm], None]
) -> GeradorDeJustificativaAdk:
    """Fábrica do gerador real: importa o ADK, monta `LlmAgent` + `Runner` e devolve a porta.

    A chave vai por `genai.Client(api_key=…)` explícito, sem tocar `os.environ` (mesma decisão
    de `criar_analista_adk`/`criar_classificador_adk`). Sem `output_schema`: a resposta é pedida
    em JSON mode e `interpretar_resposta` é quem valida contra o contrato certo.

    Args:
        config: configurações com `google_api_key`, `modelo_justificativa`.
        registrar_chamada: recebe a `ChamadaLlm` de cada chamada (quem chama grava em `traco`).

    Returns:
        Um `GeradorDeJustificativaAdk` pronto para `gerar`.

    Raises:
        ValueError: sem `GOOGLE_API_KEY`.
        ModeloSemPreco: `modelo_justificativa` sem preço tabelado (o teto diário não saberia
            contar).
    """
    if config.google_api_key is None:
        raise ValueError("GOOGLE_API_KEY ausente")
    if config.modelo_justificativa not in PRECOS_USD_POR_MILHAO:
        raise ModeloSemPreco(config.modelo_justificativa)

    from google import genai
    from google.adk.agents import LlmAgent
    from google.adk.models.google_llm import Gemini
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    modelo = Gemini(
        model=config.modelo_justificativa,
        client=genai.Client(api_key=config.google_api_key.get_secret_value()),
    )
    agente = LlmAgent(
        name="gerador_de_justificativa",
        model=modelo,
        instruction=carregar_prompt(),
        include_contents="none",
        generate_content_config=types.GenerateContentConfig(
            response_mime_type="application/json", temperature=0.2
        ),
    )
    servico = InMemorySessionService()
    runner = Runner(agent=agente, app_name=APP_ADK, session_service=servico)

    def novo_conteudo(texto: str) -> types.Content:
        return types.Content(role="user", parts=[types.Part(text=texto)])

    return GeradorDeJustificativaAdk(
        runner=runner,
        servico_sessao=servico,
        modelo=config.modelo_justificativa,
        registrar_chamada=registrar_chamada,
        novo_conteudo=novo_conteudo,
    )
