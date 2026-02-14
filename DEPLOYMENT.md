# Spraply Deployment Guide (FastAPI)

This guide describes production deployment for Spraply using Docker with FastAPI as the backend.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- Git

## Quick Start

```bash
git clone https://github.com/Abhishek-yadv/Spraply.git
cd Spraply/docker
cp .env.example .env
docker compose up -d --build
```

## Services

- `nginx`: reverse proxy entrypoint
- `app`: FastAPI backend (`uvicorn` on `9000`)
- `frontend`: static frontend service
- `db`: PostgreSQL
- `redis`: Redis
- `minio`: object storage
- `playwright`: browser automation service
- `mcp`: MCP service

## Required production variables

Set these in `docker/.env`:

- `SECRET_KEY`
- `POSTGRES_PASSWORD`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `PLAYWRIGHT_API_KEY`
- `FRONTEND_URL`
- `IS_ENTERPRISE_MODE_ACTIVE` (as needed)

Recommended:

- `AUTO_CREATE_TABLES=False`
- `NGINX_PORT` (if not 80)
- `SENTRY_*` values if Sentry is enabled

## Database migrations

The backend container runs Alembic migrations automatically at startup via `backend/docker-entrypoint.sh`.

Manual migration command:

```bash
docker compose exec app alembic upgrade head
```

## Access

- Frontend: `http://<host>/`
- API: `http://<host>/api/`
- Swagger: `http://<host>/api/schema/swagger-ui/`
- ReDoc: `http://<host>/api/schema/redoc/`
- MinIO Console: `http://<host>/minio-console/`

## Operations

### Start / stop

```bash
docker compose up -d
docker compose down
```

### Rebuild backend

```bash
docker compose build app
docker compose up -d app
```

### Logs

```bash
docker compose logs -f app
docker compose logs -f nginx
```

## Troubleshooting

- If API is not reachable, check `docker compose logs app` and verify DB health.
- If migrations fail, run `docker compose exec app alembic upgrade head` and review output.
- If uploads fail, verify MinIO credentials and bucket environment variables.
