# O que é: teste do passo 15 da V1 — `.env.example` documenta toda chave que `Configuracoes` lê
# (mais as três do Compose/testes). Quando ler: ao acrescentar campo em `config.py`.
from pathlib import Path

from aprovaos.config import Configuracoes

RAIZ = Path(__file__).resolve().parents[2]


def _chaves_do_env_example() -> set[str]:
    linhas = (RAIZ / ".env.example").read_text(encoding="utf-8").splitlines()
    return {
        linha.split("=", 1)[0].strip()
        for linha in linhas
        if linha.strip() and not linha.lstrip().startswith("#")
    }


def test_env_example_cobre_todas_as_configuracoes() -> None:
    esperadas = {campo.upper() for campo in Configuracoes.model_fields}
    esperadas |= {"DATABASE_URL_TEST", "POSTGRES_PASSWORD", "POSTGRES_PORT"}
    assert _chaves_do_env_example() == esperadas
