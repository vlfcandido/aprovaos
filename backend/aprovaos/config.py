"""Configurações do AprovaOS lidas do ambiente/.env por fábrica, nunca em import.

O que é: `Configuracoes` (pydantic-settings) e `obter_configuracoes()` com cache. Quando ler: ao
precisar de um valor de ambiente novo — acrescente o campo aqui e a chave em `.env.example`.
"""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracoes(BaseSettings):
    """Valores de ambiente do backend.

    Prioridade (pydantic-settings): argumentos do construtor > variáveis de ambiente > `.env`.
    A leitura acontece só na instanciação; importar este módulo não toca disco nem ambiente.

    Attributes:
        database_url: URL SQLAlchemy do banco (`sqlite://…` em teste, `postgresql+psycopg://…`).
        chave_secreta: segredo para assinar o cookie de sessão; nunca aparece em `repr`.
        ambiente: `dev`, `teste` ou `prod`.
        cookie_seguro: envia o cookie de sessão com `Secure` (desligar só em rede local http).
        sessao_dias: validade da sessão em dias.
        web_dir: pasta `web/` (templates e estáticos); `None` = resolvida pela app.
        uploads_dir: pasta dos PDFs subidos; `None` = `data/uploads` na raiz, resolvida pela app.
        google_api_key: chave do Gemini (AI Studio, ADR-0030); `None` = DNA só por regras.
        modelo_dna: modelo Gemini do agente `analista-de-edital` (ADR-0018: Flash; passo 12b da
            V3 — `gemini-2.5-flash` responde 404 para chaves novas, "no longer available to new
            users"; trocado para `gemini-3.6-flash`, o sucessor indicado pela própria API).
        teto_diario_brl: gasto máximo com LLM por dia, em R$ (ADR-0018); vale desde a 1ª chamada.
        documentos_dir: pasta das provas coletadas; `None` = `knowledge/provas`, resolvida pela app.
        contato_coletor: e-mail no User-Agent do coletor (ADR-0030), identificando as requisições.
        modelo_classificacao: modelo Gemini do curador de questões (ADR-0018: Flash; passo 12c —
            `gemini-3.5-flash-lite`, não `gemini-3.6-flash`: cada modelo tem cota diária própria
            no free tier, achado do passo 12b, e classificar item num vocabulário fechado é
            "simple data processing" — o Lite é o mais barato da família e a tarefa certa para
            ele; `modelo_dna` continua Flash porque o DNA do edital é raciocínio, não triagem).
        lote_classificacao: quantas questões o curador classifica por chamada ao LLM.
        modelo_justificativa: modelo Gemini do agente `gerador-de-justificativa` (fundação
            jurídica, passo 5). `gemini-3.6-flash`, não o Lite: explicar por que um gabarito é o
            que é, ancorado em dispositivo, é raciocínio — o mesmo motivo de `modelo_dna`, não
            "simple data processing" como a classificação de tópico.
        modelo_aula: modelo Gemini do agente `gerador-de-aula` (fatia 6, trilha e aulas em
            texto). `gemini-3.6-flash`, mesmo corte de `modelo_justificativa`/`modelo_dna`:
            escrever uma aula ancorada em dossiê é raciocínio, não classificação.
        modelo_questao: modelo Gemini do agente `gerador-de-questao` (fatia 5, inéditas
            validadas). `gemini-3.6-flash`, mesmo corte de `modelo_aula`/`modelo_justificativa`:
            escrever um item novo no padrão da banca, ancorado no dossiê, é raciocínio.
        modelo_validador_questao: modelo Gemini do agente `validador-de-questao` (fatia 5) — uma
            família de prompt **diferente** de `modelo_questao`, que resolve o item de novo sem
            ver o gabarito do gerador (regra 1 do produto: nada gerado chega ao aluno sem
            validação por outro agente). `gemini-3.6-flash` pelo mesmo motivo de `modelo_questao`
            — resolver a questão é raciocínio, não classificação.
        google_oauth_client_id: `Client ID` OAuth 2.0 do Google Cloud (fatia 1b, RF-20, Ruling
            42, ADR-0026); `None` = login por Google inativo (a rota `/entrar/google` devolve
            404 e o botão não aparece). Fonte: doc oficial do Google Identity, OAuth 2.0 para
            aplicações web — https://developers.google.com/identity/protocols/oauth2/web-server.
        google_oauth_client_secret: `Client Secret` do mesmo par de credenciais; `None` no mesmo
            critério de `google_oauth_client_id` (as duas nascem e morrem juntas).
        mercado_pago_access_token: token de acesso do Mercado Pago (fatia 12, RF-22, ADR-0025,
            ADR-0044); `None` = billing inativo — `/assinar` devolve 404, nenhuma tela de
            assinatura aparece, todo mundo permanece Free. Fonte:
            `github.com/mercadopago/openapi` (`spec3.json`, recurso `/preapproval`).
        mercado_pago_webhook_secret: segredo usado só para validar o HMAC do `x-signature` de
            `POST /webhooks/pagamento`; `None` no mesmo critério de `mercado_pago_access_token`
            (as duas nascem e morrem juntas — Ruling 46).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    chave_secreta: SecretStr
    ambiente: Literal["dev", "teste", "prod"] = "dev"
    cookie_seguro: bool = True
    sessao_dias: int = 30
    web_dir: Path | None = None
    uploads_dir: Path | None = None
    google_api_key: SecretStr | None = None
    modelo_dna: str = "gemini-3.6-flash"
    teto_diario_brl: Decimal = Decimal("3.00")
    documentos_dir: Path | None = None
    contato_coletor: str = "vlfcandido@gmail.com"
    modelo_classificacao: str = "gemini-3.5-flash-lite"
    lote_classificacao: int = Field(default=20, gt=0)
    modelo_justificativa: str = "gemini-3.6-flash"
    modelo_aula: str = "gemini-3.6-flash"
    modelo_questao: str = "gemini-3.6-flash"
    modelo_validador_questao: str = "gemini-3.6-flash"
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: SecretStr | None = None
    mercado_pago_access_token: SecretStr | None = None
    mercado_pago_webhook_secret: SecretStr | None = None

    @field_validator(
        "web_dir",
        "uploads_dir",
        "documentos_dir",
        "google_api_key",
        "google_oauth_client_id",
        "google_oauth_client_secret",
        "mercado_pago_access_token",
        "mercado_pago_webhook_secret",
        mode="before",
    )
    @classmethod
    def _vazio_e_ausente(cls, valor: object) -> object:
        """Trata variável vazia (`WEB_DIR=` no `.env`) como variável ausente.

        Sem isto, o pydantic-settings entrega a string vazia e cada campo opcional a converte
        num valor que **parece** preenchido: `Path("")` vira `Path(".")` (truthy, então
        `config.web_dir or raiz / "web"` em `main.py` nunca cai no padrão e o app morre com
        `Directory 'static' does not exist`) e `SecretStr("")` não é `None` (então os agentes
        montam `genai.Client(api_key="")` em vez de degradar para regras, e o billing sairia do
        estado desligado com um token vazio). Cada linha do `.env.example` promete o contrário:
        "vazio = …". Achado em 23/09/2026 ao subir o servidor pela raiz do repositório.

        Args:
            valor: o valor bruto do ambiente, do `.env` ou do construtor.

        Returns:
            `None` quando o valor é uma string só de espaços (ou vazia); o valor intacto no
            resto dos casos — inclusive `Path` e `SecretStr` já construídos.
        """
        if isinstance(valor, str) and not valor.strip():
            return None
        return valor


@lru_cache
def obter_configuracoes() -> Configuracoes:
    """Cria (uma vez por processo) e devolve as configurações lidas do ambiente.

    Returns:
        A instância única de `Configuracoes`; `obter_configuracoes.cache_clear()` descarta.
    """
    return Configuracoes()
