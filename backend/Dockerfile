# O que é: imagem do serviço web do AprovaOS (uv + Python 3.13, dependências travadas pelo uv.lock).
# Quando ler: ao mudar dependências de runtime ou o comando de subida.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# Dependências primeiro (camada cacheável), sem o pacote e sem dev.
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# Código e front.
COPY backend/ ./
COPY web/ /web/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn aprovaos.main:criar_app --factory --host 0.0.0.0 --port 8000"]
