"""Agente `classificador`: implementação ADK (Gemini) da porta `ClassificadorDeTopico`.

O que é: `ClassificadorAdk` + `criar_classificador_adk` — a única função que importa `google.*`,
e só quando chamada — e `escolher_classificador`, que decide se a IA entra (sem chave ou sem
teto → `None` com o motivo, mesmo padrão de `api.editais._escolher_analista`). O contrato
(`ClassificadorDeTopico`, `Classificacao`, `interpretar_resposta`, o fallback por regras) vive em
`aprovaos.motor.curadoria.classificacao`. Quando ler: ao ligar a classificação num pipeline real,
ao mudar o prompt, ou ao investigar por que um lote saiu "por regras".
"""

from collections.abc import Callable
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


class RespostaDoModeloAusente(RuntimeError):
    """O ADK terminou sem resposta final com texto (ou com `error_code`)."""


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
            Exception: qualquer falha do ADK/provedor, relançada após o registro.
        """
        slugs_validos = {topico.slug for topico in vocabulario}
        iniciado_em = datetime.now(UTC)
        t0 = perf_counter()
        tokens_in: int | None = None
        tokens_out: int | None = None
        try:
            resposta, tokens_in, tokens_out = await self._rodar(montar_mensagem(itens, vocabulario))
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
