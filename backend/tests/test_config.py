# O que é: testes do passo 2 da V1 — `Configuracoes` só lê ambiente quando instanciada.
# Quando ler: ao adicionar campo de configuração ou mudar a fábrica `obter_configuracoes`.
from decimal import Decimal

import pydantic
import pytest
from pydantic import SecretStr

from aprovaos.config import Configuracoes, obter_configuracoes

CHAVE = "x" * 32


def test_configuracoes_aceita_valores_explicitos() -> None:
    cfg = Configuracoes(database_url="sqlite://", chave_secreta=SecretStr(CHAVE), _env_file=None)
    assert cfg.ambiente == "dev"
    assert cfg.cookie_seguro is True
    assert cfg.sessao_dias == 30
    assert cfg.web_dir is None


def test_configuracoes_le_variaveis_de_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("CHAVE_SECRETA", CHAVE)
    cfg = Configuracoes(_env_file=None)
    assert cfg.database_url == "sqlite://"
    assert cfg.chave_secreta.get_secret_value() == CHAVE


def test_configuracoes_exige_obrigatorias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CHAVE_SECRETA", raising=False)
    with pytest.raises(pydantic.ValidationError):
        Configuracoes(_env_file=None)


def test_obter_configuracoes_e_cacheada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("CHAVE_SECRETA", CHAVE)
    obter_configuracoes.cache_clear()
    try:
        assert obter_configuracoes() is obter_configuracoes()
    finally:
        obter_configuracoes.cache_clear()


def test_chave_secreta_nao_vaza_em_repr() -> None:
    cfg = Configuracoes(database_url="sqlite://", chave_secreta=SecretStr(CHAVE), _env_file=None)
    assert isinstance(cfg.chave_secreta, SecretStr)
    assert CHAVE not in repr(cfg)
    assert CHAVE not in str(cfg)


def test_configuracoes_da_v2_tem_padroes() -> None:
    cfg = Configuracoes(database_url="sqlite://", chave_secreta=SecretStr(CHAVE), _env_file=None)
    assert cfg.uploads_dir is None
    assert cfg.google_api_key is None
    assert cfg.modelo_dna == "gemini-3.6-flash"
    assert cfg.teto_diario_brl == Decimal("3.00")


def test_google_api_key_e_secreta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "abc")
    cfg = Configuracoes(database_url="sqlite://", chave_secreta=SecretStr(CHAVE), _env_file=None)
    assert isinstance(cfg.google_api_key, SecretStr)
    assert cfg.google_api_key.get_secret_value() == "abc"
    assert "abc" not in repr(cfg)


def test_campos_da_v3() -> None:
    cfg = Configuracoes(database_url="sqlite://", chave_secreta=SecretStr(CHAVE), _env_file=None)
    assert cfg.documentos_dir is None
    assert cfg.contato_coletor == "vlfcandido@gmail.com"
    assert cfg.modelo_classificacao == "gemini-3.6-flash"
    assert cfg.lote_classificacao == 20
    with pytest.raises(pydantic.ValidationError):
        Configuracoes(
            database_url="sqlite://",
            chave_secreta=SecretStr(CHAVE),
            lote_classificacao=0,
            _env_file=None,
        )
