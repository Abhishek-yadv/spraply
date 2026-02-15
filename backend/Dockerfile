FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY README.md ./README.md
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN pip install --upgrade pip && \
    pip install . && \
    sed -i 's/\r$//' /app/docker-entrypoint.sh && \
    chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
