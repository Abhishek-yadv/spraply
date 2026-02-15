# Spraply Development Setup Guide

This guide explains how to run Spraply with the FastAPI backend locally.

## Prerequisites

- Python 3.13+
- Node.js 20+
- pnpm
- Docker + Docker Compose

## Windows notes (important)

If you're on Windows and run Linux containers with Docker Desktop, make sure shell scripts in this repo use LF line endings. Otherwise containers can fail with errors like `no such file or directory` when executing entrypoints.

After pulling the latest changes (which include a `.gitattributes`), run once:

```bash
git add --renormalize .
```

Then commit the normalization (or stash/discard if you're not committing) and re-run your Docker commands.

## Quick Setup

```bash
./scripts/setup-dev.sh
```

## Manual Setup

### 1) Start local infra

```bash
cd docker
docker compose -f docker-compose.local.yml up -d
```

### 2) Setup FastAPI backend

```bash
cd ../backend
python3 -m pip install -e .
alembic upgrade head
```

### 3) Setup frontend

```bash
cd ../frontend
pnpm install
```

## Run development servers

### FastAPI backend

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
pnpm run dev
```

## Access points

- Frontend: [http://localhost:5173](http://localhost:5173)
- API: [http://localhost:8000/api](http://localhost:8000/api)
- Swagger: [http://localhost:8000/api/schema/swagger-ui/](http://localhost:8000/api/schema/swagger-ui/)
- ReDoc: [http://localhost:8000/api/schema/redoc/](http://localhost:8000/api/schema/redoc/)
- MinIO Console: [http://localhost:9001](http://localhost:9001)
- Mailpit: [http://localhost:8025](http://localhost:8025)

## Notes

- Database schema is managed by Alembic in `backend/alembic`.
- `docker-compose.local.yml` only starts infra services; run API/frontend from host for development.
