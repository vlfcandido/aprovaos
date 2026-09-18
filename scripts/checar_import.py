"""Prova de que importar qualquer módulo de `aprovaos` não faz rede, banco nem lê ambiente.

O que é: script de verificação (roda na CI e em `scripts/checar.sh`): limpa as variáveis de
configuração, bloqueia `socket.connect` e `sqlalchemy.create_engine`, importa todos os
submódulos e imprime `importados: N`. Quando ler: quando ele falhar — um módulo ganhou efeito
colateral em import; corrija movendo o trabalho para uma fábrica chamada em `criar_app()`.

Uso: `uv run --project backend python scripts/checar_import.py`
"""

import importlib
import os
import pkgutil
import socket
import sys
import traceback
from typing import Any

PREFIXOS_PROIBIDOS = ("DATABASE_URL", "CHAVE_SECRETA", "AMBIENTE")


def _proibido(*args: Any, **kwargs: Any) -> Any:
    """Substitui rede e engine durante o import; qualquer chamada é efeito colateral.

    Raises:
        RuntimeError: sempre.
    """
    raise RuntimeError("efeito colateral em import: rede ou create_engine")


def _limpar_ambiente() -> None:
    """Remove do ambiente toda variável de configuração do AprovaOS."""
    for chave in list(os.environ):
        if chave.startswith(PREFIXOS_PROIBIDOS):
            del os.environ[chave]


def _sabotar() -> None:
    """Bloqueia `socket.connect` e `sqlalchemy.create_engine` para o resto do processo."""
    socket.socket.connect = _proibido  # type: ignore[method-assign]
    import sqlalchemy

    sqlalchemy.create_engine = _proibido


def importar_tudo() -> int:
    """Importa `aprovaos` e todos os submódulos, recursivamente.

    Returns:
        Quantidade de módulos importados (incluindo o pacote raiz).
    """
    import aprovaos

    total = 1
    for info in pkgutil.walk_packages(aprovaos.__path__, "aprovaos."):
        importlib.import_module(info.name)
        total += 1
    return total


def main() -> None:
    """Executa a verificação e sai com 0 (limpo) ou 1 (efeito colateral detectado)."""
    _limpar_ambiente()
    _sabotar()
    try:
        total = importar_tudo()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
    print(f"importados: {total}")
    sys.exit(0)


if __name__ == "__main__":
    main()
