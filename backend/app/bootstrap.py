from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Plan


def ensure_default_plans(db: Session) -> None:
    existing = db.scalar(select(Plan).limit(1))
    if existing:
        return

    free_plan = Plan(
        uuid=uuid4(),
        name="Free",
        label="Starter",
        group="monthly",
        description="Free starter plan",
        price_before_discount=None,
        price=0,
        stripe_price_id="",
        number_of_users=1,
        page_credit=1000,
        daily_page_credit=100,
        crawl_max_depth=3,
        crawl_max_limit=100,
        max_concurrent_crawl=1,
        is_default=True,
        order=1,
        is_active=True,
    )
    pro_plan = Plan(
        uuid=uuid4(),
        name="Pro",
        label="Scale",
        group="monthly",
        description="Paid plan with higher limits",
        price_before_discount=None,
        price=49,
        stripe_price_id="local_pro",
        number_of_users=10,
        page_credit=100000,
        daily_page_credit=5000,
        crawl_max_depth=10,
        crawl_max_limit=10000,
        max_concurrent_crawl=10,
        is_default=False,
        order=2,
        is_active=True,
    )
    db.add(free_plan)
    db.add(pro_plan)
    db.commit()
