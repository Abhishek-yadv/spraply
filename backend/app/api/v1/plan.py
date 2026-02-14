from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.dependencies import get_current_team, get_current_user
from app.models import Plan, PlanFeature, StripeWebhookHistory, Subscription, Team, TeamMember, User


router = APIRouter()


class PlanFeatureOut(BaseModel):
    title: str
    help_text: str | None
    icon: str | None


class PlanOut(BaseModel):
    uuid: UUID
    name: str
    label: str | None
    group: str
    description: str
    price_before_discount: float | None
    price: float
    number_of_users: int
    page_credit: int
    daily_page_credit: int
    crawl_max_depth: int
    crawl_max_limit: int
    max_concurrent_crawl: int
    is_default: bool
    features: list[PlanFeatureOut]


class StripeWebhookIn(BaseModel):
    type: str
    data: dict


class StartSubscriptionIn(BaseModel):
    plan_uuid: UUID


class SubscriptionPlanOut(BaseModel):
    uuid: UUID
    name: str
    label: str | None
    group: str
    description: str
    price_before_discount: float | None
    price: float
    number_of_users: int
    page_credit: int
    daily_page_credit: int
    crawl_max_depth: int
    crawl_max_limit: int
    max_concurrent_crawl: int
    is_default: bool
    features: list[PlanFeatureOut]


class SubscriptionOut(BaseModel):
    uuid: UUID
    plan: SubscriptionPlanOut
    status: str
    remain_page_credit: int
    remain_daily_page_credit: int
    start_at: datetime | None
    current_period_start_at: datetime | None
    current_period_end_at: datetime | None
    cancel_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TeamPlanOut(BaseModel):
    plan_name: str
    status: str
    plan_page_credit: int
    plan_daily_page_credit: int
    plan_number_users: int
    remain_number_users: int
    remaining_page_credit: int
    remaining_daily_page_credit: int
    max_depth: int
    max_concurrent_crawl: int
    start_at: datetime | None
    current_period_start_at: datetime | None
    current_period_end_at: datetime | None
    cancel_at: datetime | None
    is_default: bool


def _serialize_plan(plan: Plan, features: list[PlanFeature]) -> PlanOut:
    return PlanOut(
        uuid=plan.uuid,
        name=plan.name,
        label=plan.label,
        group=plan.group,
        description=plan.description,
        price_before_discount=float(plan.price_before_discount) if plan.price_before_discount is not None else None,
        price=float(plan.price),
        number_of_users=plan.number_of_users,
        page_credit=plan.page_credit,
        daily_page_credit=plan.daily_page_credit,
        crawl_max_depth=plan.crawl_max_depth,
        crawl_max_limit=plan.crawl_max_limit,
        max_concurrent_crawl=plan.max_concurrent_crawl,
        is_default=plan.is_default,
        features=[PlanFeatureOut(title=f.title, help_text=f.help_text, icon=f.icon) for f in features],
    )


def _serialize_subscription(subscription: Subscription, plan: Plan, features: list[PlanFeature]) -> SubscriptionOut:
    return SubscriptionOut(
        uuid=subscription.uuid,
        status=subscription.status,
        remain_page_credit=subscription.remain_page_credit,
        remain_daily_page_credit=subscription.remain_daily_page_credit,
        start_at=subscription.start_at,
        current_period_start_at=subscription.current_period_start_at,
        current_period_end_at=subscription.current_period_end_at,
        cancel_at=subscription.cancel_at,
        created_at=subscription.created_at,
        updated_at=subscription.updated_at,
        plan=SubscriptionPlanOut(
            uuid=plan.uuid,
            name=plan.name,
            label=plan.label,
            group=plan.group,
            description=plan.description,
            price_before_discount=float(plan.price_before_discount) if plan.price_before_discount is not None else None,
            price=float(plan.price),
            number_of_users=plan.number_of_users,
            page_credit=plan.page_credit,
            daily_page_credit=plan.daily_page_credit,
            crawl_max_depth=plan.crawl_max_depth,
            crawl_max_limit=plan.crawl_max_limit,
            max_concurrent_crawl=plan.max_concurrent_crawl,
            is_default=plan.is_default,
            features=[PlanFeatureOut(title=f.title, help_text=f.help_text, icon=f.icon) for f in features],
        ),
    )


def _get_active_subscription(db: Session, team: Team) -> Subscription | None:
    return db.scalar(
        select(Subscription)
        .where(Subscription.team_id == team.uuid, Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
    )


@router.get("/plans/", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)) -> list[PlanOut]:
    plans = db.scalars(select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.order.asc())).all()
    response: list[PlanOut] = []
    for plan in plans:
        features = db.scalars(select(PlanFeature).where(PlanFeature.plan_id == plan.uuid).order_by(PlanFeature.order.asc())).all()
        response.append(_serialize_plan(plan, features))
    return response


@router.get("/plans/{plan_uuid}/", response_model=PlanOut)
def retrieve_plan(plan_uuid: UUID, db: Session = Depends(get_db)) -> PlanOut:
    plan = db.scalar(select(Plan).where(Plan.uuid == plan_uuid, Plan.is_active.is_(True)))
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    features = db.scalars(select(PlanFeature).where(PlanFeature.plan_id == plan.uuid).order_by(PlanFeature.order.asc())).all()
    return _serialize_plan(plan, features)


protected_router = APIRouter()


@protected_router.get("/subscriptions/", response_model=list[SubscriptionOut])
def list_subscriptions(
    team: Team = Depends(get_current_team),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SubscriptionOut]:
    rows = db.scalars(select(Subscription).where(Subscription.team_id == team.uuid).order_by(Subscription.created_at.desc())).all()
    result: list[SubscriptionOut] = []
    for item in rows:
        plan = db.get(Plan, item.plan_id)
        if not plan:
            continue
        features = db.scalars(select(PlanFeature).where(PlanFeature.plan_id == plan.uuid).order_by(PlanFeature.order.asc())).all()
        result.append(_serialize_subscription(item, plan, features))
    return result


@protected_router.get("/subscriptions/{subscription_uuid}/", response_model=SubscriptionOut)
def retrieve_subscription(
    subscription_uuid: UUID,
    team: Team = Depends(get_current_team),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionOut:
    item = db.scalar(select(Subscription).where(Subscription.uuid == subscription_uuid, Subscription.team_id == team.uuid))
    if not item:
        raise HTTPException(status_code=404, detail="Subscription not found")
    plan = db.get(Plan, item.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    features = db.scalars(select(PlanFeature).where(PlanFeature.plan_id == plan.uuid).order_by(PlanFeature.order.asc())).all()
    return _serialize_subscription(item, plan, features)


@protected_router.get("/subscriptions/current", response_model=TeamPlanOut)
def current_subscription(
    team: Team = Depends(get_current_team),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamPlanOut:
    if not settings.is_enterprise_mode_active:
        return TeamPlanOut(
            plan_name="Unlimited",
            status="active",
            plan_page_credit=-1,
            plan_daily_page_credit=-1,
            plan_number_users=-1,
            remain_number_users=-1,
            remaining_page_credit=-1,
            remaining_daily_page_credit=-1,
            max_depth=-1,
            max_concurrent_crawl=-1,
            start_at=None,
            current_period_start_at=None,
            current_period_end_at=None,
            cancel_at=None,
            is_default=False,
        )

    subscription = _get_active_subscription(db, team)
    if not subscription:
        raise HTTPException(status_code=404, detail="You have no active subscription")

    plan = subscription.plan
    return TeamPlanOut(
        plan_name=plan.name,
        status=subscription.status,
        plan_page_credit=plan.page_credit,
        plan_daily_page_credit=plan.daily_page_credit,
        plan_number_users=plan.number_of_users,
        remain_number_users=max(
            0,
            plan.number_of_users
            - (
                db.scalar(
                    select(func.count()).select_from(TeamMember).where(TeamMember.team_id == team.uuid)
                )
                or 0
            ),
        ),
        remaining_page_credit=subscription.remain_page_credit,
        remaining_daily_page_credit=subscription.remain_daily_page_credit,
        max_depth=plan.crawl_max_depth,
        max_concurrent_crawl=plan.max_concurrent_crawl,
        start_at=subscription.start_at,
        current_period_start_at=subscription.current_period_start_at,
        current_period_end_at=subscription.current_period_end_at,
        cancel_at=subscription.cancel_at,
        is_default=plan.is_default,
    )


@protected_router.post("/subscriptions/start")
def start_subscription(
    payload: StartSubscriptionIn,
    team: Team = Depends(get_current_team),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not settings.is_enterprise_mode_active:
        raise HTTPException(status_code=403, detail="Subscriptions are disabled in non-enterprise mode")

    plan = db.scalar(select(Plan).where(Plan.uuid == payload.plan_uuid, Plan.is_active.is_(True)))
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    current = _get_active_subscription(db, team)
    if current:
        current.status = "canceled"
        current.cancel_at = datetime.now(UTC)
        db.add(current)

    subscription = Subscription(
        uuid=uuid4(),
        team_id=team.uuid,
        stripe_subscription_id=f"local_{uuid4()}",
        plan_id=plan.uuid,
        remain_page_credit=plan.page_credit,
        remain_daily_page_credit=plan.daily_page_credit,
        start_at=datetime.now(UTC),
        current_period_start_at=datetime.now(UTC),
        current_period_end_at=datetime.now(UTC),
        status="active",
    )
    db.add(subscription)
    db.commit()

    if plan.is_default:
        return {"started": True}
    return {"redirect_url": "https://payments.example.com/checkout"}


@protected_router.delete("/subscriptions/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_subscription(
    team: Team = Depends(get_current_team),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    sub = _get_active_subscription(db, team)
    if sub:
        sub.status = "canceled"
        sub.cancel_at = datetime.now(UTC)
        db.add(sub)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@protected_router.post("/subscriptions/renew", status_code=status.HTTP_204_NO_CONTENT)
def renew_subscription(
    team: Team = Depends(get_current_team),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    sub = _get_active_subscription(db, team)
    if not sub:
        raise HTTPException(status_code=404, detail="You have no active subscription")
    sub.status = "active"
    sub.cancel_at = None
    db.add(sub)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@protected_router.post("/subscriptions/manage-subscription")
def manage_subscription(
    _: Team = Depends(get_current_team),
    __: User = Depends(get_current_user),
) -> dict:
    return {"redirect_url": "https://payments.example.com/manage"}


@router.post("/webhook/stripe/", status_code=status.HTTP_204_NO_CONTENT)
def stripe_webhook(payload: StripeWebhookIn, db: Session = Depends(get_db)) -> Response:
    event = StripeWebhookHistory(uuid=uuid4(), data=payload.model_dump())
    db.add(event)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


router.include_router(protected_router)
