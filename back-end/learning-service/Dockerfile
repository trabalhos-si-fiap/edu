FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# O container reproduz a MESMA disposição relativa do repositório
# (/app/learning-service ao lado de /app/packages/edu-common), para que o
# path `../packages/edu-common` do [tool.uv.sources] valha no host e aqui
# dentro sem precisar de source condicional.
WORKDIR /app/learning-service

COPY packages/edu-common /app/packages/edu-common
COPY learning-service/pyproject.toml learning-service/uv.lock* ./
RUN uv sync --no-install-project

# O modelo de embeddings entra na imagem, não no primeiro request: sem isto
# o container baixa ~470MB do Hugging Face na primeira chamada que precisa
# dele e, sem internet, degrada em silêncio. Fica antes do COPY do código
# para a camada sobreviver a qualquer mudança em app/. O nome tem que ser o
# mesmo de `NOME_MODELO` em app/services/embeddings.py.
RUN uv run --no-sync python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"

COPY learning-service/ ./

CMD ["uv", "run", "granian", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", "app.main:app"]
