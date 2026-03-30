FROM python:3.13-slim AS base

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1

RUN pip install --no-cache-dir poetry==2.3.2

COPY pyproject.toml poetry.lock* ./
RUN poetry install --only=main --no-root

# ── Production ────────────────────────────────────────────────────────────────
FROM base AS prod
COPY src/ ./src/
CMD ["poetry", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]

# ── Development (hot-reload, deps include dev group) ──────────────────────────
FROM base AS dev
RUN poetry install --no-root
COPY src/ ./src/
CMD ["poetry", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002", "--reload"]
