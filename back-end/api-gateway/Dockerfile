FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Mesma disposição relativa do repositório: o contexto de build é `back-end/`,
# então o serviço vive em /app/<service>. O gateway não copia
# packages/edu-common — ele é um proxy burro e não valida JWT.
WORKDIR /app/api-gateway

COPY api-gateway/pyproject.toml api-gateway/uv.lock* ./
RUN uv sync --no-install-project

COPY api-gateway/ ./

CMD ["uv", "run", "granian", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", "app.main:app"]
