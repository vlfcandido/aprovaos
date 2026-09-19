"""Agente `gerador-de-questao`: porta, ADK (Gemini) e interpretação da resposta (fatia 5).

O que é: `GeradorDeQuestao` (porta assíncrona), `carregar_prompt`/`montar_mensagem`,
`interpretar_resposta` e `criar_gerador_adk` — a única função que importa `google.*`, e só
quando chamada. Mesmo padrão de `aprovaos.agentes.gerador_de_aula` e
`aprovaos.agentes.gerador_de_justificativa`: `LlmAgent` com JSON mode (sem `output_schema` — o
Developer API do Gemini rejeita o `additionalProperties` que os `list`/`Union` deste contrato
viram em JSON Schema), `include_contents="none"`, prompt em arquivo versionado.

**Uma chamada gera um único item** (Ruling 44, `docs/fatias/5-questoes-ineditas.md`): o plano do
lote inteiro (`dominio.questao_inedita.montar_plano_do_lote`) já decide, por regra, o mecanismo e
o gabarito de cada item antes de qualquer chamada ao modelo — `EntradaGeradorQuestao` carrega
essa prescrição (`mecanismo_alvo`/`gabarito_alvo`), e o agente só escreve o item pedido. Isso
mantém o custo em duas chamadas por item (esta e a do `validador-de-questao`) e reduz a chance de
`dominio.questao_inedita.conferir_lote` apontar divergência, já que o plano não depende do
modelo se autodisciplinar sobre um lote inteiro numa resposta só.

**Não há implementação "por regras" desta porta** — escrever um item novo no padrão da banca,
ancorado em dossiê, não é algo que um léxico determinístico saiba fazer; o "nunca bloqueia" aqui
é papel de quem chama (`aprovaos.motor.gerar_questao`): um item cuja geração falhar (rede, cota,
resposta fora do contrato) simplesmente não é produzido nesta rodada — resultado correto, não
erro do comando.

Quando ler: ao ligar o agente ao comando `motor.gerar_questao`, ao mudar o prompt, ou ao
investigar por que um item saiu vazio/reprovado.
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
from aprovaos.dominio.questao_inedita import EntradaGeradorQuestao, QuestaoGerada
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

NOME_AGENTE = "gerador-de-questao"
APP_ADK = "aprovaos"
_CERCA_DE_CODIGO = re.compile(r"\A```[a-zA-Z]*\s*\n?(.*?)\n?```\Z", re.DOTALL)


@runtime_checkable
class GeradorDeQuestao(Protocol):
    """Porta do gerador: recebe o dossiê/originais/mecanismo-alvo e devolve um único item."""

    async def gerar(self, entrada: EntradaGeradorQuestao) -> QuestaoGerada:
        """Gera um item inédito (ainda não validado por `validador-de-questao`).

        Args:
            entrada: as fontes do dossiê, até cinco originais de referência e o mecanismo/
                gabarito já prescritos pelo plano do lote — a única matéria-prima que o modelo
                pode usar.

        Returns:
            `QuestaoGerada` interpretado da resposta do modelo.
        """
        ...


def carregar_prompt() -> str:
    """Lê `prompts/gerador-de-questao.md` do disco (chamado pela fábrica, nunca em import).

    Returns:
        O prompt estático (o dossiê, os originais e o mecanismo/gabarito-alvo vão na mensagem).
    """
    return (Path(__file__).parent / "prompts" / "gerador-de-questao.md").read_text(encoding="utf-8")


def montar_mensagem(entrada: EntradaGeradorQuestao) -> str:
    """Monta a mensagem do usuário: dossiê, originais de referência e o alvo deste item.

    Args:
        entrada: a `EntradaGeradorQuestao` deste item.

    Returns:
        Texto com uma linha por fonte (`F-n | citacao_canonica | trecho`), até cinco originais
        (`enunciado | gabarito`) e o mecanismo/gabarito prescritos.
    """
    linhas = [
        f"topico_slug: {entrada.topico_slug}",
        f"banca_alvo: {entrada.banca_alvo}",
        f"tipo_item: {entrada.tipo_item}",
    ]
    linhas.append(f"\n## Fontes do dossiê ({len(entrada.fontes)} linhas: F-n | citacao | trecho)")
    for fonte in entrada.fontes:
        linhas.append(f"{fonte.id} | {fonte.citacao_canonica} | {fonte.trecho}")

    if entrada.originais:
        linhas.append(
            f"\n## Questões originais de referência ({len(entrada.originais)}: enunciado | "
            "gabarito)"
        )
        for original in entrada.originais:
            linhas.append(f"{original.enunciado} | {original.gabarito}")

    linhas.append(f"\nmecanismo_alvo: {entrada.mecanismo_alvo}")
    linhas.append(f"gabarito_alvo: {entrada.gabarito_alvo}")
    linhas.append(f"aderencia_medida: {'true' if entrada.aderencia_medida else 'false'}")
    return "\n".join(linhas) + "\n"


def interpretar_resposta(texto: str) -> QuestaoGerada:
    """Converte a resposta do modelo em `QuestaoGerada`, tolerando cerca de código.

    Args:
        texto: resposta bruta (JSON de um único item, possivelmente entre ```json … ```).

    Returns:
        `QuestaoGerada` validado contra o contrato.

    Raises:
        pydantic.ValidationError: a resposta não cumpre o contrato esperado.
        json.JSONDecodeError: a resposta (depois de remover a cerca) não é JSON.
    """
    limpo = texto.strip()
    cercado = _CERCA_DE_CODIGO.match(limpo)
    if cercado is not None:
        limpo = cercado.group(1).strip()
    return QuestaoGerada.model_validate(json.loads(limpo))


class RespostaDoModeloAusente(RuntimeError):
    """O ADK terminou sem resposta final com texto (ou com `error_code`)."""


class GeradorDeQuestaoAdk:
    """Implementação da porta com `LlmAgent` + `Runner` do ADK; nasce só em `criar_gerador_adk`.

    Cada `gerar` abre uma sessão nova em memória, roda o agente uma vez, entrega ao callback uma
    `ChamadaLlm` (sucesso ou erro) e devolve o item interpretado — ainda **sem** validação por
    `validador-de-questao`; quem chama (`aprovaos.motor.gerar_questao`) roda a resolução
    independente e `dominio.validacao_questao.julgar` antes de gravar qualquer coisa.
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

    async def gerar(self, entrada: EntradaGeradorQuestao) -> QuestaoGerada:
        """Roda o agente uma vez e devolve o item interpretado.

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
            app_name=APP_ADK, user_id="gerador-de-questao", session_id=str(uuid4())
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
) -> GeradorDeQuestaoAdk:
    """Fábrica do gerador real: importa o ADK, monta `LlmAgent` + `Runner` e devolve a porta.

    A chave vai por `genai.Client(api_key=…)` explícito, sem tocar `os.environ` (mesma decisão
    de `criar_gerador_adk` da aula/justificativa). Sem `output_schema`: a resposta é pedida em
    JSON mode e `interpretar_resposta` é quem valida contra o contrato certo.

    Args:
        config: configurações com `google_api_key`, `modelo_questao`.
        registrar_chamada: recebe a `ChamadaLlm` de cada chamada (quem chama grava em `traco`).

    Returns:
        Um `GeradorDeQuestaoAdk` pronto para `gerar`.

    Raises:
        ValueError: sem `GOOGLE_API_KEY`.
        ModeloSemPreco: `modelo_questao` sem preço tabelado (o teto diário não saberia contar).
    """
    if config.google_api_key is None:
        raise ValueError("GOOGLE_API_KEY ausente")
    if config.modelo_questao not in PRECOS_USD_POR_MILHAO:
        raise ModeloSemPreco(config.modelo_questao)

    from google import genai
    from google.adk.agents import LlmAgent
    from google.adk.models.google_llm import Gemini
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    modelo = Gemini(
        model=config.modelo_questao,
        client=genai.Client(api_key=config.google_api_key.get_secret_value()),
    )
    agente = LlmAgent(
        name="gerador_de_questao",
        model=modelo,
        instruction=carregar_prompt(),
        include_contents="none",
        generate_content_config=types.GenerateContentConfig(
            response_mime_type="application/json", temperature=0.4
        ),
    )
    servico = InMemorySessionService()
    runner = Runner(agent=agente, app_name=APP_ADK, session_service=servico)

    def novo_conteudo(texto: str) -> types.Content:
        return types.Content(role="user", parts=[types.Part(text=texto)])

    return GeradorDeQuestaoAdk(
        runner=runner,
        servico_sessao=servico,
        modelo=config.modelo_questao,
        registrar_chamada=registrar_chamada,
        novo_conteudo=novo_conteudo,
    )
