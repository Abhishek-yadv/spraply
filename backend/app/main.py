from copy import deepcopy

from fastapi import FastAPI

from app.api.router import api_router
from app.bootstrap import ensure_default_plans
from app.config import settings
from app.db import Base, SessionLocal, engine
from app import models  # noqa: F401


app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,
    docs_url="/api/schema/swagger-ui/",
    redoc_url="/api/schema/redoc/",
    openapi_url="/api/schema/",
)

app.include_router(api_router)


@app.on_event("startup")
def startup() -> None:
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_default_plans(db)
    finally:
        db.close()


@app.get("/api/schema/team/")
def team_schema() -> dict:
    base = deepcopy(app.openapi())
    base.setdefault("components", {}).setdefault("securitySchemes", {})[
        "ApiKeyAuth"
    ] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "Team API key header",
    }
    return base
