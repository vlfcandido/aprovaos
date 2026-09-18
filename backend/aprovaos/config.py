"""Configurações do AprovaOS lidas do ambiente/.env por fábrica, nunca em import.

O que é: `Configuracoes` (pydantic-settings) e `obter_configuracoes()` com cache. Quando ler: ao
precisar de um valor de ambiente novo — acrescente o campo aqui e a chave em `.env.example`.
"""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
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
        modelo_classificacao: modelo Gemini do curador de questões (ADR-0018: Flash; mesma troca
            do passo 12b — `gemini-3.6-flash`).
        lote_classificacao: quantas questões o curador classifica por chamada ao LLM.
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
    modelo_classificacao: str = "gemini-3.6-flash"
    lote_classificacao: int = Field(default=20, gt=0)


@lru_cache
def obter_configuracoes() -> Configuracoes:
    """Cria (uma vez por processo) e devolve as configurações lidas do ambiente.

    Returns:
        A instância única de `Configuracoes`; `obter_configuracoes.cache_clear()` descarta.
    """
    return Configuracoes()
