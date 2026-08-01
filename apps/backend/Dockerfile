# syntax=docker/dockerfile:1

FROM python:3.14-slim AS base

# instala o uv copiando o binário oficial (forma recomendada pela Astral)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# usa o Python já instalado na imagem, evitando download do CPython gerenciado pelo uv
ENV UV_PYTHON_PREFERENCE=only-system

# copia só os arquivos de dependências primeiro (cache de layer)
COPY apps/backend/pyproject.toml apps/backend/uv.lock ./

RUN uv sync --frozen --no-dev

# copia o resto do código do backend
COPY apps/backend/ .

# garante que o venv criado pelo uv está no PATH
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# ajuste "app.main:app" para o caminho real do seu módulo, se for diferente
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --forwarded-allow-ips="*""]