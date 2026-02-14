# Spraply FastAPI Backend

This directory is the full FastAPI replacement backend for Spraply.

## Included

- PostgreSQL persistence with SQLAlchemy ORM
- Alembic migrations (`alembic/`)
- JWT authentication (`access` + `refresh`) and team/API-key auth
- API groups aligned with previous Spraply paths:
  - `/api/v1/user/`
  - `/api/v1/common/`
  - `/api/v1/core/`
  - `/api/v1/plan/`
- OpenAPI/docs paths:
  - `/api/schema/`
  - `/api/schema/swagger-ui/`
  - `/api/schema/redoc/`
  - `/api/schema/team/`

## Environment

Set environment variables (or create `.env` in this directory):

```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/Spraply
SECRET_KEY=change-me
IS_ENTERPRISE_MODE_ACTIVE=false
IS_LOGIN_ACTIVE=true
IS_SIGNUP_ACTIVE=true
AUTO_CREATE_TABLES=false
```

## Run locally

From `backend`:

```bash
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Optional quick boot

If you want table creation on startup without Alembic (dev only):

```bash
AUTO_CREATE_TABLES=true uvicorn app.main:app --reload
```
