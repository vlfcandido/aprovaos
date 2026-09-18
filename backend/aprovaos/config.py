"""Configurações do AprovaOS lidas do ambiente/.env por fábrica, nunca em import.

O que é: `Configuracoes` (pydantic-settings) e `obter_configuracoes()` com cache. Quando ler: ao
precisar de um valor de ambiente novo — acrescente o campo aqui e a chave em `.env.example`.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
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
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    chave_secreta: SecretStr
    ambiente: Literal["dev", "teste", "prod"] = "dev"
    cookie_seguro: bool = True
    sessao_dias: int = 30
    web_dir: Path | None = None


@lru_cache
def obter_configuracoes() -> Configuracoes:
    """Cria (uma vez por processo) e devolve as configurações lidas do ambiente.

    Returns:
        A instância única de `Configuracoes`; `obter_configuracoes.cache_clear()` descarta.
    """
    return Configuracoes()
