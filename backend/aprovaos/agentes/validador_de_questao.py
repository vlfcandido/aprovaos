"""Agente `validador-de-questao`: porta, ADK (Gemini) e interpretação da resposta (fatia 5).

O que é: `ValidadorDeQuestao` (porta assíncrona), `carregar_prompt`/`montar_mensagem`,
`interpretar_resposta` e `criar_validador_adk` — a única função que importa `google.*`, e só
quando chamada. Mesmo padrão dos outros agentes ADK do repositório (`LlmAgent` com JSON mode,
`include_contents="none"`, prompt em arquivo versionado).

**É outra família de prompt, nunca o mesmo agente do `gerador-de-questao` se auto-aprovando**
(regra 1 do produto, "nada gerado chega ao aluno sem validação"): `EntradaValidadorQuestao` é
deliberadamente mais pobre que a entrada do gerador — sem `gabarito`, sem `trecho_que_decide`,
sem `mecanismo`. O validador resolve o item de novo, só com o que um candidato veria na prova e
o dossiê; `dominio.validacao_questao.julgar` compara essa resolução independente com o gabarito
do gerador (item 1 do validador da skill `gerador-questao-banca`).

**Não há implementação "por regras" desta porta** — resolver um item de prova exige o mesmo
raciocínio que escrevê-lo; o "nunca bloqueia" aqui é papel de quem chama
(`aprovaos.motor.gerar_questao`): um item cuja resolução independente falhar (rede, cota,
resposta fora do contrato) vira item reprovado com o motivo, nunca publicado.

Quando ler: ao ligar o agente ao comando `motor.gerar_questao`, ao mudar o prompt, ou ao
investigar por que um item foi reprovado por divergência de gabarito.
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
from aprovaos.dominio.validacao_questao import EntradaValidadorQuestao, ResolucaoValidador
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

NOME_AGENTE = "validador-de-questao"
APP_ADK = "aprovaos"
_CERCA_DE_CODIGO = re.compile(r"\A```[a-zA-Z]*\s*\n?(.*?)\n?```\Z", re.DOTALL)


@runtime_checkable
class ValidadorDeQuestao(Protocol):
    """Porta do validador: recebe o item sem gabarito e devolve a resolução independente."""

    async def resolver(self, entrada: EntradaValidadorQuestao) -> ResolucaoValidador:
        """Resolve o item de forma independente, sem ver o gabarito do gerador.

        Args:
            entrada: comando/enunciado/alternativas e o dossiê — nunca o gabarito, o
                `trecho_que_decide` ou o mecanismo escolhidos pelo `gerador-de-questao`.

        Returns:
            `ResolucaoValidador` com o gabarito a que este agente chegou por conta própria.
        """
        ...


def carregar_prompt() -> str:
    """Lê `prompts/validador-de-questao.md` do disco (chamado pela fábrica, nunca em import).

    Returns:
        O prompt estático (o item e o dossiê vão na mensagem do usuário).
    """
    return (Path(__file__).parent / "prompts" / "validador-de-questao.md").read_text(
        encoding="utf-8"
    )


def montar_mensagem(entrada: EntradaValidadorQuestao) -> str:
    """Monta a mensagem do usuário: o item (sem gabarito) e o dossiê.

    Args:
        entrada: a `EntradaValidadorQuestao` deste item.

    Returns:
        Texto com `tipo_item`, comando/enunciado, alternativas (quando houver) e a lista
        `F-n | citacao_canonica | trecho` das fontes — nunca o gabarito nem o `trecho_que_decide`
        que o gerador escolheu (esses campos nem existem em `EntradaValidadorQuestao`).
    """
    linhas = [f"tipo_item: {entrada.tipo_item}"]
    if entrada.comando:
        linhas.append(f"comando: {entrada.comando}")
    linhas.append(f"enunciado: {entrada.enunciado}")
    if entrada.alternativas is not None:
        linhas.append(f"\n## Alternativas ({len(entrada.alternativas)} linhas: letra | texto)")
        for alternativa in entrada.alternativas:
            linhas.append(f"{alternativa.letra} | {alternativa.texto}")
    linhas.append(f"\n## Fontes do dossiê ({len(entrada.fontes)} linhas: F-n | citacao | trecho)")
    for fonte in entrada.fontes:
        linhas.append(f"{fonte.id} | {fonte.citacao_canonica} | {fonte.trecho}")
    return "\n".join(linhas) + "\n"


def interpretar_resposta(texto: str) -> ResolucaoValidador:
    """Converte a resposta do modelo em `ResolucaoValidador`, tolerando cerca de código.

    Args:
        texto: resposta bruta (JSON, possivelmente entre ```json … ```).

    Returns:
        `ResolucaoValidador` validado contra o contrato.

    Raises:
        pydantic.ValidationError: a resposta não cumpre o contrato esperado.
        json.JSONDecodeError: a resposta (depois de remover a cerca) não é JSON.
    """
    limpo = texto.strip()
    cercado = _CERCA_DE_CODIGO.match(limpo)
    if cercado is not None:
        limpo = cercado.group(1).strip()
    return ResolucaoValidador.model_validate(json.loads(limpo))


class RespostaDoModeloAusente(RuntimeError):
    """O ADK terminou sem resposta final com texto (ou com `error_code`)."""


class ValidadorDeQuestaoAdk:
    """Implementação da porta com `LlmAgent` + `Runner` do ADK; nasce só em `criar_validador_adk`.

    Cada `resolver` abre uma sessão nova em memória, roda o agente uma vez, entrega ao callback
    uma `ChamadaLlm` (sucesso ou erro) e devolve a resolução interpretada.
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

    async def resolver(self, entrada: EntradaValidadorQuestao) -> ResolucaoValidador:
        """Roda o agente uma vez e devolve a resolução interpretada.

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
            resposta, tokens_in, tokens_out = await self._rodar(montar_mensagem(entrada))
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
        return interpretar_resposta(resposta)

    async def _rodar(self, mensagem: str) -> tuple[str, int | None, int | None]:
        """Executa o runner numa sessão nova e devolve (texto final, tokens_in, tokens_out)."""
        sessao = await self._servico_sessao.create_session(
            app_name=APP_ADK, user_id="validador-de-questao", session_id=str(uuid4())
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


def criar_validador_adk(
    config: Configuracoes, registrar_chamada: Callable[[ChamadaLlm], None]
) -> ValidadorDeQuestaoAdk:
    """Fábrica do validador real: importa o ADK, monta `LlmAgent` + `Runner` e devolve a porta.

    A chave vai por `genai.Client(api_key=…)` explícito, sem tocar `os.environ`. Sem
    `output_schema`: a resposta é pedida em JSON mode e `interpretar_resposta` é quem valida
    contra o contrato certo.

    Args:
        config: configurações com `google_api_key`, `modelo_validador_questao`.
        registrar_chamada: recebe a `ChamadaLlm` de cada chamada (quem chama grava em `traco`).

    Returns:
        Um `ValidadorDeQuestaoAdk` pronto para `resolver`.

    Raises:
        ValueError: sem `GOOGLE_API_KEY`.
        ModeloSemPreco: `modelo_validador_questao` sem preço tabelado (o teto diário não saberia
            contar).
    """
    if config.google_api_key is None:
        raise ValueError("GOOGLE_API_KEY ausente")
    if config.modelo_validador_questao not in PRECOS_USD_POR_MILHAO:
        raise ModeloSemPreco(config.modelo_validador_questao)

    from google import genai
    from google.adk.agents import LlmAgent
    from google.adk.models.google_llm import Gemini
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    modelo = Gemini(
        model=config.modelo_validador_questao,
        client=genai.Client(api_key=config.google_api_key.get_secret_value()),
    )
    agente = LlmAgent(
        name="validador_de_questao",
        model=modelo,
        instruction=carregar_prompt(),
        include_contents="none",
        generate_content_config=types.GenerateContentConfig(
            response_mime_type="application/json", temperature=0.0
        ),
    )
    servico = InMemorySessionService()
    runner = Runner(agent=agente, app_name=APP_ADK, session_service=servico)

    def novo_conteudo(texto: str) -> types.Content:
        return types.Content(role="user", parts=[types.Part(text=texto)])

    return ValidadorDeQuestaoAdk(
        runner=runner,
        servico_sessao=servico,
        modelo=config.modelo_validador_questao,
        registrar_chamada=registrar_chamada,
        novo_conteudo=novo_conteudo,
    )
