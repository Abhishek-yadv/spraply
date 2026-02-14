from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def now_utc() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(150), default="")
    last_name: Mapped[str] = mapped_column(String(150), default="")
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    reset_password_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reset_password_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_verification_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    privacy_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terms_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    newsletter_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)


class Team(Base, TimestampMixin):
    __tablename__ = "teams"

    uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class TeamMember(Base, TimestampMixin):
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_member"),)

    uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.uuid", ondelete="CASCADE"))
    team_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("teams.uuid", ondelete="CASCADE"))
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(User)
    team: Mapped[Team] = relationship(Team)


class TeamInvitation(Base, TimestampMixin):
    __tablename__ = "team_invitations"
    __table_args__ = (UniqueConstraint("team_id", "email", name="uq_team_invitation_email"),)

    uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    team_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("teams.uuid", ondelete="CASCADE"))
    invitation_token: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    activated: Mapped[bool] = mapped_column(Boolean, default=False)

    team: Mapped[Team] = relationship(Team)


class TeamAPIKey(Base, TimestampMixin):
    __tablename__ = "team_api_keys"

    uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    team_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("teams.uuid", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    team: Mapped[Team] = relationship(Team)


class CrawlRequest(Base, TimestampMixin):
    __tablename__ = "crawl_requests"

    uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    team_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("teams.uuid", ondelete="CASCADE"), index=True)
    urls: Mapped[list] = mapped_column(JSON, default=list)
    crawl_type: Mapped[str] = mapped_column(String(50), default="single")
    status: Mapped[str] = mapped_column(String(50), default="new", index=True)
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sitemap_path: Mapped[str | None] = mapped_column(String(255), nullable=True)


class CrawlResult(Base, TimestampMixin):
    __tablename__ = "crawl_results"

    uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("crawl_requests.uuid", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(2048))
    result_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class CrawlResultAttachment(Base, TimestampMixin):
    __tablename__ = "crawl_result_attachments"

    uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    crawl_result_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("crawl_results.uuid", ondelete="CASCADE"), index=True)
    attachment_type: Mapped[str] = mapped_column(String(255))
    attachment_path: Mapped[str] = mapped_column(String(511))


class SearchRequest(Base, TimestampMixin):
    __tablename__ = "search_requests"

    uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    team_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("teams.uuid", ondelete="CASCADE"), index=True)
    query: Mapped[str] = mapped_column(String(255))
    search_options: Mapped[dict] = mapped_column(JSON, default=dict)
    result_limit: Mapped[int] = mapped_column(Integer, default=5)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="new", index=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ProxyServer(Base, TimestampMixin):
    __tablename__ = "proxy_servers"
    __table_args__ = (UniqueConstraint("team_id", "slug", name="uq_proxy_team_slug"),)

    uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str] = mapped_column(String(255), default="general")
    proxy_type: Mapped[str] = mapped_column(String(255), default="http")
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=0)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(Text, nullable=True)
    team_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("teams.uuid", ondelete="CASCADE"), nullable=True, index=True)


class SitemapRequest(Base, TimestampMixin):
    __tablename__ = "sitemap_requests"

    uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    team_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("teams.uuid", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(255))
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="new", index=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Plan(Base, TimestampMixin):
    __tablename__ = "plans"

    uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100))
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    group: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    price_before_discount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    stripe_price_id: Mapped[str] = mapped_column(String(255), default="")
    number_of_users: Mapped[int] = mapped_column(Integer, default=1)
    page_credit: Mapped[int] = mapped_column(Integer, default=1000)
    daily_page_credit: Mapped[int] = mapped_column(Integer, default=100)
    crawl_max_depth: Mapped[int] = mapped_column(Integer, default=3)
    crawl_max_limit: Mapped[int] = mapped_column(Integer, default=100)
    max_concurrent_crawl: Mapped[int] = mapped_column(Integer, default=1)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PlanFeature(Base, TimestampMixin):
    __tablename__ = "plan_features"

    uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("plans.uuid", ondelete="CASCADE"), index=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(100))
    help_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    team_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("teams.uuid", ondelete="CASCADE"), index=True)
    stripe_subscription_id: Mapped[str] = mapped_column(String(255), index=True)
    plan_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("plans.uuid", ondelete="RESTRICT"), index=True)
    remain_page_credit: Mapped[int] = mapped_column(Integer, default=0)
    remain_daily_page_credit: Mapped[int] = mapped_column(Integer, default=0)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(255), default="active", index=True)

    plan: Mapped[Plan] = relationship(Plan)


class StripeWebhookHistory(Base, TimestampMixin):
    __tablename__ = "stripe_webhook_histories"

    uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class UsageHistory(Base, TimestampMixin):
    __tablename__ = "usage_histories"

    uuid: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    team_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("teams.uuid", ondelete="RESTRICT"), index=True)
    crawl_request_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("crawl_requests.uuid", ondelete="RESTRICT"), nullable=True)
    search_request_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("search_requests.uuid", ondelete="RESTRICT"), nullable=True)
    sitemap_request_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("sitemap_requests.uuid", ondelete="RESTRICT"), nullable=True)
    requested_page_credit: Mapped[int] = mapped_column(Integer)
    used_page_credit: Mapped[int] = mapped_column(Integer)
