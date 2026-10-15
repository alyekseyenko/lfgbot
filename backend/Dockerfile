FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY app ./app
COPY migrations ./migrations
COPY tests ./tests
COPY scripts ./scripts
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN pip install --upgrade pip \
    && pip install ".[dev]" \
    && chmod +x docker-entrypoint.sh scripts/ensure-db.sh

CMD ["./docker-entrypoint.sh"]
