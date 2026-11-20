# --- Build: installa le dipendenze in un virtualenv, con Poetry ---------------------
FROM python:3.12-slim AS build

ENV POETRY_VERSION=2.4.3 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PIP_NO_CACHE_DIR=1

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

# Prima solo i file delle dipendenze: lo strato resta in cache finché non cambiano
COPY pyproject.toml poetry.lock README.md LICENSE ./
RUN poetry install --only main --no-root

COPY src ./src
RUN poetry install --only main


# --- Runtime: solo Python, il virtualenv e il codice, senza Poetry -----------------
FROM python:3.12-slim

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Il server non gira come root
RUN useradd --create-home --uid 10001 app
COPY --from=build --chown=app:app /app /app
USER app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"

CMD ["uvicorn", "travel_agent_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
