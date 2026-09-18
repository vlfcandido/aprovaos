#!/usr/bin/env bash
# O que é: a checagem completa do AprovaOS — o mesmo que a CI roda (lint, formato, tipos, prova de
# import sem efeito colateral, testes). Quando ler: antes de qualquer commit; se falhar, não commite.
set -euo pipefail
cd "$(dirname "$0")/../backend"

etapa() { printf '\n== %s ==\n' "$1"; }

etapa "1/5 ruff check";          uv run ruff check . ../scripts
etapa "2/5 ruff format --check"; uv run ruff format --check . ../scripts
etapa "3/5 mypy";                uv run mypy
etapa "4/5 import sem efeito colateral"; uv run python ../scripts/checar_import.py
etapa "5/5 pytest";              uv run pytest -q

printf '\ncheckagem completa: OK\n'
