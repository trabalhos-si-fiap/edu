FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# O container reproduz a MESMA disposição relativa do repositório
# (/app/analytics-service ao lado de /app/packages/edu-common), para que
# o path `../packages/edu-common` do [tool.uv.sources] valha no host e aqui
# dentro sem precisar de source condicional.
WORKDIR /app/analytics-service

COPY packages/edu-common /app/packages/edu-common
COPY analytics-service/pyproject.toml analytics-service/uv.lock* ./
RUN uv sync --no-install-project

COPY analytics-service/ ./

CMD ["uv", "run", "granian", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", "app.main:app"]
