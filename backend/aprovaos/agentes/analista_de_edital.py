"""Agente `analista-de-edital`: porta, implementação por regras, ADK (Gemini) e o fallback.

O que é: `AnalistaDeEdital` (porta assíncrona), `AnalistaPorRegras`, `gerar_dna` (IA →
`verificar_dna` → regras, nunca bloqueia), `carregar_prompt`/`montar_mensagem`,
`interpretar_resposta` e `criar_analista_adk` — a única função que importa `google.*`, e só
quando chamada. Quando ler: ao ligar o agente numa rota, ao mudar o prompt ou ao investigar por
que um DNA saiu "por regras" (`ResultadoDna.motivo_fallback`).
"""

import re
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel

from aprovaos.config import Configuracoes
from aprovaos.dominio.dna import DnaConcurso, montar_dna_por_regras, verificar_dna
from aprovaos.dominio.edital import MateriaExtraida
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

NOME_AGENTE = "analista-de-edital"
APP_ADK = "aprovaos"
_CERCA_DE_CODIGO = re.compile(r"\A```[a-zA-Z]*\s*\n?(.*?)\n?```\Z", re.DOTALL)


@runtime_checkable
class AnalistaDeEdital(Protocol):
    """Porta do analista: recebe o edital e os tópicos extraídos e devolve o `DnaConcurso`."""

    async def analisar(self, texto: str, materias: list[MateriaExtraida]) -> DnaConcurso:
        """Monta o DNA do concurso.

        Args:
            texto: texto integral do edital.
            materias: conteúdo programático já extraído pelo parser (slugs calculados).

        Returns:
            O DNA no contrato da skill `dna-do-concurso` (ainda sem `verificar_dna`).
        """
        ...


class AnalistaPorRegras:
    """Implementação determinística da porta: `montar_dna_por_regras`, sem modelo."""

    async def analisar(self, texto: str, materias: list[MateriaExtraida]) -> DnaConcurso:
        """Monta o DNA só com os fatos do edital (ver `montar_dna_por_regras`)."""
        return montar_dna_por_regras(texto, materias)


class ResultadoDna(BaseModel):
    """O que `gerar_dna` devolve: o DNA e de onde ele veio.

    Attributes:
        dna: o DNA aprovado por `verificar_dna` (IA) ou o das regras.
        origem: `ia` ou `regras`.
        motivo_fallback: por que caiu para regras (`None` quando `origem == "ia"`).
    """

    dna: DnaConcurso
    origem: Literal["ia", "regras"]
    motivo_fallback: str | None


async def gerar_dna(
    texto: str,
    materias: list[MateriaExtraida],
    analista_ia: AnalistaDeEdital | None,
    motivo_sem_ia: str | None,
) -> ResultadoDna:
    """Gera o DNA pela IA quando há analista e o resultado passa; senão, por regras.

    Args:
        texto: texto integral do edital.
        materias: conteúdo programático extraído pelo parser.
        analista_ia: implementação da porta com modelo, ou `None` (sem chave / teto atingido).
        motivo_sem_ia: motivo registrado quando `analista_ia` é `None`.

    Returns:
        `ResultadoDna` com `origem` e `motivo_fallback`; nunca levanta por falha do modelo.
    """
    if analista_ia is None:
        return ResultadoDna(
            dna=montar_dna_por_regras(texto, materias),
            origem="regras",
            motivo_fallback=motivo_sem_ia,
        )
    try:
        dna = await analista_ia.analisar(texto, materias)
    except Exception as erro:  # noqa: BLE001 — deliberado: qualquer falha do provedor
        # (rede, cota, resposta fora do esquema) degrada para regras — arquitetura §8, "nunca
        # bloquear". Só o tipo vai para o motivo, para não vazar detalhe do provedor.
        motivo = f"erro na IA: {type(erro).__name__}"
        return ResultadoDna(
            dna=montar_dna_por_regras(texto, materias), origem="regras", motivo_fallback=motivo
        )
    problemas = verificar_dna(dna, materias)
    if problemas:
        motivo = "DNA da IA reprovado: " + "; ".join(problemas)
        return ResultadoDna(
            dna=montar_dna_por_regras(texto, materias), origem="regras", motivo_fallback=motivo
        )
    return ResultadoDna(dna=dna, origem="ia", motivo_fallback=None)


def carregar_prompt() -> str:
    """Lê `prompts/analista-de-edital.md` do disco (chamado pela fábrica, nunca em import).

    Returns:
        O prompt estático (os dados do edital vão na mensagem do usuário).
    """
    return (Path(__file__).parent / "prompts" / "analista-de-edital.md").read_text(encoding="utf-8")


def montar_mensagem(texto: str, materias: list[MateriaExtraida]) -> str:
    """Monta a mensagem do usuário: o edital e a lista `slug | materia | texto_original`.

    Args:
        texto: texto integral do edital.
        materias: conteúdo programático extraído pelo parser.

    Returns:
        Texto com o edital e uma linha por tópico, para o modelo usar os slugs dados.
    """
    linhas = [
        f"{topico.slug} | {materia.slug} | {topico.texto_original}"
        for materia in materias
        for topico in materia.topicos
    ]
    return (
        "## Texto do edital\n\n"
        f"{texto}\n\n"
        f"## Tópicos do conteúdo programático ({len(linhas)} linhas: slug | materia | "
        "texto_original)\n\n" + "\n".join(linhas) + "\n"
    )


def interpretar_resposta(texto: str) -> DnaConcurso:
    """Converte a resposta do modelo em `DnaConcurso`, tolerando cerca de código.

    Args:
        texto: resposta bruta (JSON, possivelmente entre ```json … ```).

    Returns:
        O DNA validado.

    Raises:
        pydantic.ValidationError: se o JSON não cumprir o contrato.
    """
    limpo = texto.strip()
    cercado = _CERCA_DE_CODIGO.match(limpo)
    if cercado is not None:
        limpo = cercado.group(1).strip()
    return DnaConcurso.model_validate_json(limpo)


class RespostaDoModeloAusente(RuntimeError):
    """O ADK terminou sem resposta final com texto (ou com `error_code`)."""


class AnalistaAdk:
    """Implementação da porta com `LlmAgent` + `Runner` do ADK; nasce só em `criar_analista_adk`.

    Cada `analisar` abre uma sessão nova em memória, roda o agente uma vez, entrega ao callback
    uma `ChamadaLlm` (sucesso ou erro) e devolve o DNA interpretado. O fallback é de `gerar_dna`.
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

    async def analisar(self, texto: str, materias: list[MateriaExtraida]) -> DnaConcurso:
        """Roda o agente uma vez e devolve o DNA; registra a chamada mesmo em erro.

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
            resposta, tokens_in, tokens_out = await self._rodar(montar_mensagem(texto, materias))
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
            app_name=APP_ADK, user_id="analista", session_id=str(uuid4())
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


def criar_analista_adk(
    config: Configuracoes, registrar_chamada: Callable[[ChamadaLlm], None]
) -> AnalistaAdk:
    """Fábrica do analista real: importa o ADK, monta `LlmAgent` + `Runner` e devolve a porta.

    A chave vai por `genai.Client(api_key=…)` explícito (premissa I da V2; `Gemini.client`
    conferido no google-adk 2.9.1), sem tocar `os.environ`. Sem `output_schema` (Q4, plano B): o
    Gemini Developer API rejeita `additionalProperties`, que é como os `dict` do DNA viram JSON
    Schema; a resposta é pedida em JSON mode (`response_mime_type="application/json"`,
    https://googleapis.github.io/python-genai/genai.html#genai.types.GenerateContentConfig) com o
    esquema descrito no prompt, e `interpretar_resposta` é quem valida contra `DnaConcurso`.

    Args:
        config: configurações com `google_api_key`, `modelo_dna`.
        registrar_chamada: recebe a `ChamadaLlm` de cada chamada (a rota grava em `traco`).

    Returns:
        Um `AnalistaAdk` pronto para `analisar`.

    Raises:
        ValueError: sem `GOOGLE_API_KEY`.
        ModeloSemPreco: `modelo_dna` sem preço tabelado (o teto diário não saberia contar).
    """
    if config.google_api_key is None:
        raise ValueError("GOOGLE_API_KEY ausente")
    if config.modelo_dna not in PRECOS_USD_POR_MILHAO:
        raise ModeloSemPreco(config.modelo_dna)

    from google import genai
    from google.adk.agents import LlmAgent
    from google.adk.models.google_llm import Gemini
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    modelo = Gemini(
        model=config.modelo_dna,
        client=genai.Client(api_key=config.google_api_key.get_secret_value()),
    )
    agente = LlmAgent(
        name="analista_de_edital",
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

    return AnalistaAdk(
        runner=runner,
        servico_sessao=servico,
        modelo=config.modelo_dna,
        registrar_chamada=registrar_chamada,
        novo_conteudo=novo_conteudo,
    )
