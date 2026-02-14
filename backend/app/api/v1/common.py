from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User


router = APIRouter()


class FrontendSettings(BaseModel):
    is_enterprise_mode_active: bool
    github_client_id: str
    google_client_id: str
    is_signup_active: bool
    is_login_active: bool
    is_google_login_active: bool
    is_github_login_active: bool
    api_version: str
    policy_url: str
    terms_url: str
    policy_update_at: datetime
    terms_update_at: datetime
    google_analytics_id: str
    is_installed: bool
    is_search_configured: bool
    max_crawl_concurrency: int
    mcp_server: str


@router.get("/settings/", response_model=FrontendSettings)
def get_settings(db: Session = Depends(get_db)) -> FrontendSettings:
    users_count = db.scalar(select(func.count()).select_from(User)) or 0
    now = datetime.now(UTC)
    return FrontendSettings(
        is_enterprise_mode_active=settings.is_enterprise_mode_active,
        github_client_id=settings.github_client_id,
        google_client_id=settings.google_client_id,
        is_signup_active=settings.is_signup_active,
        is_login_active=settings.is_login_active,
        is_google_login_active=settings.is_google_login_active,
        is_github_login_active=settings.is_github_login_active,
        api_version=settings.api_version,
        policy_url=settings.policy_url,
        terms_url=settings.terms_url,
        policy_update_at=now,
        terms_update_at=now,
        google_analytics_id=settings.google_analytics_id,
        is_installed=users_count > 0,
        is_search_configured=False,
        max_crawl_concurrency=settings.max_crawl_concurrency,
        mcp_server=settings.mcp_server,
    )
