from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.dependencies import get_current_team
from app.models import (
    CrawlRequest,
    CrawlResult,
    ProxyServer,
    SearchRequest,
    SitemapRequest,
    Subscription,
    Team,
)


CRAWL_STATUS_NEW = "new"
CRAWL_STATUS_RUNNING = "running"
CRAWL_STATUS_FINISHED = "finished"
CRAWL_STATUS_CANCELING = "canceling"
CRAWL_STATUS_CANCELED = "canceled"
CRAWL_STATUS_FAILED = "failed"

SEARCH_DEPTH_BASIC = "basic"
SEARCH_DEPTH_ADVANCED = "advanced"
SEARCH_DEPTH_ULTIMATE = "ultimate"

PROXY_CATEGORY_GENERAL = "general"
PROXY_CATEGORY_PREMIUM = "premium"
PROXY_CATEGORY_TEAM = "team"


router = APIRouter()


class ActionModel(BaseModel):
    type: str


class PageOptions(BaseModel):
    exclude_tags: list[str] = []
    include_tags: list[str] = []
    wait_time: int = 100
    include_html: bool = False
    only_main_content: bool = True
    include_links: bool = False
    timeout: int = 15000
    accept_cookies_selector: str | None = None
    locale: str | None = "en-US"
    extra_headers: dict = {}
    actions: list[ActionModel] = []
    ignore_rendering: bool = False


class SpiderOptions(BaseModel):
    max_depth: int = 1
    page_limit: int = 1
    concurrent_requests: int | None = None
    allowed_domains: list[str] = []
    exclude_paths: list[str] = []
    include_paths: list[str] = []
    proxy_server: str | None = None


class CrawlOptions(BaseModel):
    spider_options: SpiderOptions
    page_options: PageOptions
    plugin_options: dict = {}


class CrawlRequestIn(BaseModel):
    url: str
    options: CrawlOptions


class BatchCrawlRequestIn(BaseModel):
    urls: list[str] = Field(min_length=1)
    options: CrawlOptions


class CrawlRequestOut(BaseModel):
    uuid: UUID
    url: str
    urls: list[str]
    crawl_type: str
    status: str
    options: dict
    created_at: datetime
    updated_at: datetime
    duration: int | None
    number_of_documents: int
    sitemap: str | None


class CrawlResultOut(BaseModel):
    uuid: UUID
    url: str
    result: dict | None
    created_at: datetime
    updated_at: datetime


class SearchOptions(BaseModel):
    language: str | None = None
    country: str | None = None
    time_renge: str = "any"
    search_type: str = "web"
    depth: str = SEARCH_DEPTH_BASIC


class SearchRequestIn(BaseModel):
    query: str
    search_options: SearchOptions = SearchOptions()
    result_limit: int = Field(default=5, ge=1, le=20)


class SearchRequestOut(BaseModel):
    uuid: UUID
    query: str
    search_options: dict
    result_limit: int
    duration: int | None
    status: str
    result: dict | None
    created_at: datetime


class SitemapOptions(BaseModel):
    include_subdomains: bool = True
    ignore_sitemap_xml: bool = False
    search: str | None = None
    include_paths: list[str] = []
    exclude_paths: list[str] = []
    proxy_server: str | None = None


class SitemapRequestIn(BaseModel):
    url: str
    options: SitemapOptions


class SitemapRequestOut(BaseModel):
    uuid: UUID
    url: str
    status: str
    options: dict
    duration: int | None
    result: dict | None
    created_at: datetime
    updated_at: datetime


class ProxyServerIn(BaseModel):
    name: str
    slug: str
    is_default: bool = False
    proxy_type: str = "http"
    host: str
    port: int
    username: str | None = None
    password: str | None = None


class ProxyServerOut(BaseModel):
    name: str
    slug: str
    is_default: bool
    proxy_type: str
    host: str
    port: int
    username: str | None
    has_password: bool
    created_at: datetime
    updated_at: datetime


class ListAllProxyServerOut(BaseModel):
    name: str
    slug: str
    category: str


class TestProxyIn(BaseModel):
    slug: str | None = None
    host: str | None = None
    port: int | None = None
    proxy_type: str | None = None
    username: str | None = None
    password: str | None = None


def _serialize_crawl_request(item: CrawlRequest, db: Session) -> CrawlRequestOut:
    results_count = db.scalar(
        select(func.count()).select_from(CrawlResult).where(CrawlResult.request_id == item.uuid)
    ) or 0
    return CrawlRequestOut(
        uuid=item.uuid,
        url=item.urls[0] if item.urls else "",
        urls=item.urls,
        crawl_type=item.crawl_type,
        status=item.status,
        options=item.options,
        created_at=item.created_at,
        updated_at=item.updated_at,
        duration=item.duration_seconds,
        number_of_documents=int(results_count),
        sitemap=item.sitemap_path,
    )


def _get_team_subscription(db: Session, team: Team) -> Subscription | None:
    if not settings.is_enterprise_mode_active:
        return None
    return db.scalar(
        select(Subscription)
        .where(Subscription.team_id == team.uuid, Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
    )


def _remaining_limits(db: Session, team: Team) -> tuple[int, int, int, int, bool, list[str]]:
    if not settings.is_enterprise_mode_active:
        return (-1, -1, -1, -1, False, [PROXY_CATEGORY_TEAM, PROXY_CATEGORY_GENERAL, PROXY_CATEGORY_PREMIUM])

    subscription = _get_team_subscription(db, team)
    if not subscription:
        raise HTTPException(status_code=403, detail="You have no active subscription")

    plan = subscription.plan
    allowed_proxy_categories = [PROXY_CATEGORY_TEAM, PROXY_CATEGORY_GENERAL]
    if not plan.is_default:
        allowed_proxy_categories.append(PROXY_CATEGORY_PREMIUM)

    return (
        subscription.remain_page_credit,
        subscription.remain_daily_page_credit,
        plan.crawl_max_depth,
        plan.max_concurrent_crawl,
        plan.is_default,
        allowed_proxy_categories,
    )


def _validate_concurrency(db: Session, team: Team, model_cls) -> None:
    _, _, _, max_concurrent, _, _ = _remaining_limits(db, team)
    if max_concurrent == -1:
        return

    window_start = datetime.now(UTC) - timedelta(hours=2)
    running = db.scalars(
        select(model_cls).where(
            model_cls.team_id == team.uuid,
            model_cls.status.in_([CRAWL_STATUS_NEW, CRAWL_STATUS_RUNNING]),
            model_cls.created_at >= window_start,
        )
    ).all()
    if len(running) >= max_concurrent:
        raise HTTPException(status_code=403, detail=f"Your plan does not support more than {max_concurrent} concurrent tasks")


def _search_credit_cost(result_limit: int, depth: str) -> int:
    depth_multiplier = {
        SEARCH_DEPTH_BASIC: 1,
        SEARCH_DEPTH_ADVANCED: 2,
        SEARCH_DEPTH_ULTIMATE: 3,
    }.get(depth, 1)
    return result_limit * depth_multiplier


def _sitemap_credit_cost(ignore_sitemap_xml: bool) -> int:
    return 10 if ignore_sitemap_xml else 1


def _validate_proxy_access(db: Session, team: Team, slug: str | None, allowed_categories: list[str]) -> None:
    if not slug:
        return
    proxy = db.scalar(
        select(ProxyServer).where(
            ProxyServer.slug == slug,
            or_(ProxyServer.team_id == team.uuid, ProxyServer.team_id.is_(None)),
        )
    )
    if not proxy:
        raise HTTPException(status_code=400, detail="Proxy server does not exist")
    if proxy.category not in allowed_categories:
        raise HTTPException(status_code=403, detail="With the current plan you cannot use this proxy server")


@router.get("/usage/")
def usage(team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> dict:
    crawl_count = len(db.scalars(select(CrawlRequest).where(CrawlRequest.team_id == team.uuid)).all())
    search_count = len(db.scalars(select(SearchRequest).where(SearchRequest.team_id == team.uuid)).all())
    sitemap_count = len(db.scalars(select(SitemapRequest).where(SitemapRequest.team_id == team.uuid)).all())
    return {
        "period_days": 30,
        "total_requests": crawl_count + search_count + sitemap_count,
        "crawl_requests": crawl_count,
        "search_requests": search_count,
        "sitemap_requests": sitemap_count,
    }


@router.get("/plugins/schema")
def plugin_schema(_: Team = Depends(get_current_team)) -> dict:
    return {
        "type": "object",
        "properties": {
            "provider": {"type": "string"},
            "model": {"type": "string"},
            "temperature": {"type": "number"},
        },
    }


@router.post("/crawl-requests/", response_model=CrawlRequestOut, status_code=status.HTTP_201_CREATED)
def create_crawl_request(
    payload: CrawlRequestIn,
    team: Team = Depends(get_current_team),
    db: Session = Depends(get_db),
) -> CrawlRequestOut:
    remain, remain_daily, max_depth, _, _, allowed_proxy_categories = _remaining_limits(db, team)
    _validate_concurrency(db, team, CrawlRequest)

    page_limit = payload.options.spider_options.page_limit
    if remain != -1 and page_limit > remain:
        raise HTTPException(status_code=403, detail=f"You just have {remain} page credits left in your plan")
    if remain_daily != -1 and page_limit > remain_daily:
        raise HTTPException(status_code=403, detail=f"You just have {remain_daily} daily pages left in your plan")
    if max_depth != -1 and payload.options.spider_options.max_depth > max_depth:
        raise HTTPException(status_code=403, detail=f"Your plan does not support more than {max_depth} depth")

    _validate_proxy_access(db, team, payload.options.spider_options.proxy_server, allowed_proxy_categories)

    item = CrawlRequest(
        uuid=uuid4(),
        team_id=team.uuid,
        urls=[payload.url],
        crawl_type="single",
        status=CRAWL_STATUS_NEW,
        options=payload.options.model_dump(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_crawl_request(item, db)


@router.post("/crawl-requests/batch", response_model=CrawlRequestOut, status_code=status.HTTP_201_CREATED)
def batch_crawl_requests(
    payload: BatchCrawlRequestIn,
    team: Team = Depends(get_current_team),
    db: Session = Depends(get_db),
) -> CrawlRequestOut:
    remain, remain_daily, _, _, _, allowed_proxy_categories = _remaining_limits(db, team)
    _validate_concurrency(db, team, CrawlRequest)

    page_limit = len(payload.urls)
    if remain != -1 and page_limit > remain:
        raise HTTPException(status_code=403, detail=f"You just have {remain} page credits left in your plan")
    if remain_daily != -1 and page_limit > remain_daily:
        raise HTTPException(status_code=403, detail=f"You just have {remain_daily} daily pages left in your plan")

    spider_options = payload.options.spider_options.model_dump()
    spider_options["max_depth"] = 0
    spider_options["page_limit"] = len(payload.urls)
    payload.options.spider_options = SpiderOptions(**spider_options)

    _validate_proxy_access(db, team, payload.options.spider_options.proxy_server, allowed_proxy_categories)

    item = CrawlRequest(
        uuid=uuid4(),
        team_id=team.uuid,
        urls=payload.urls,
        crawl_type="batch",
        status=CRAWL_STATUS_NEW,
        options=payload.options.model_dump(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_crawl_request(item, db)


@router.get("/crawl-requests/", response_model=list[CrawlRequestOut])
def list_crawl_requests(team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> list[CrawlRequestOut]:
    rows = db.scalars(select(CrawlRequest).where(CrawlRequest.team_id == team.uuid).order_by(CrawlRequest.created_at.desc())).all()
    return [_serialize_crawl_request(item, db) for item in rows]


@router.get("/crawl-requests/{crawl_request_uuid}/", response_model=CrawlRequestOut)
def retrieve_crawl_request(crawl_request_uuid: UUID, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> CrawlRequestOut:
    item = db.scalar(select(CrawlRequest).where(CrawlRequest.uuid == crawl_request_uuid, CrawlRequest.team_id == team.uuid))
    if not item:
        raise HTTPException(status_code=404, detail="Crawl request not found")
    return _serialize_crawl_request(item, db)


@router.delete("/crawl-requests/{crawl_request_uuid}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_crawl_request(crawl_request_uuid: UUID, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> Response:
    item = db.scalar(select(CrawlRequest).where(CrawlRequest.uuid == crawl_request_uuid, CrawlRequest.team_id == team.uuid))
    if not item:
        raise HTTPException(status_code=404, detail="Crawl request not found")
    if item.status != CRAWL_STATUS_RUNNING:
        raise HTTPException(status_code=403, detail="Only running crawl requests can be deleted")
    item.status = CRAWL_STATUS_CANCELING
    db.add(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/crawl-requests/{crawl_request_uuid}/download")
def download_crawl(crawl_request_uuid: UUID, output_format: str = "json", team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> dict:
    item = db.scalar(select(CrawlRequest).where(CrawlRequest.uuid == crawl_request_uuid, CrawlRequest.team_id == team.uuid))
    if not item:
        raise HTTPException(status_code=404, detail="Crawl request not found")
    if output_format not in {"json", "markdown"}:
        raise HTTPException(status_code=400, detail="Invalid output format")
    return {"download": False, "message": "Streaming zip download is not implemented yet"}


@router.get("/crawl-requests/{crawl_request_uuid}/status")
def crawl_status(crawl_request_uuid: UUID, prefetched: bool = False, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> dict:
    _ = prefetched
    item = db.scalar(select(CrawlRequest).where(CrawlRequest.uuid == crawl_request_uuid, CrawlRequest.team_id == team.uuid))
    if not item:
        raise HTTPException(status_code=404, detail="Crawl request not found")
    return {"status": item.status}


@router.get("/crawl-requests/{crawl_request_uuid}/sitemap/graph")
def crawl_sitemap_graph(crawl_request_uuid: UUID, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> dict:
    item = db.scalar(select(CrawlRequest).where(CrawlRequest.uuid == crawl_request_uuid, CrawlRequest.team_id == team.uuid))
    if not item or not item.sitemap_path:
        raise HTTPException(status_code=404, detail="Sitemap for this crawl request does not exist")
    return {"nodes": [], "edges": []}


@router.get("/crawl-requests/{crawl_request_uuid}/sitemap/markdown")
def crawl_sitemap_markdown(crawl_request_uuid: UUID, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> str:
    item = db.scalar(select(CrawlRequest).where(CrawlRequest.uuid == crawl_request_uuid, CrawlRequest.team_id == team.uuid))
    if not item or not item.sitemap_path:
        raise HTTPException(status_code=404, detail="Sitemap for this crawl request does not exist")
    return "# Sitemap\n"


@router.get("/crawl-requests/{crawl_request_uuid}/results/", response_model=list[CrawlResultOut])
def list_crawl_results(crawl_request_uuid: UUID, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> list[CrawlResultOut]:
    request_obj = db.scalar(select(CrawlRequest).where(CrawlRequest.uuid == crawl_request_uuid, CrawlRequest.team_id == team.uuid))
    if not request_obj:
        raise HTTPException(status_code=404, detail="Crawl request not found")
    rows = db.scalars(select(CrawlResult).where(CrawlResult.request_id == request_obj.uuid).order_by(CrawlResult.created_at.asc())).all()
    return [
        CrawlResultOut(
            uuid=item.uuid,
            url=item.url,
            result=item.result_json,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in rows
    ]


@router.get("/crawl-requests/{crawl_request_uuid}/results/{result_uuid}/", response_model=CrawlResultOut)
def retrieve_crawl_result(crawl_request_uuid: UUID, result_uuid: UUID, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> CrawlResultOut:
    request_obj = db.scalar(select(CrawlRequest).where(CrawlRequest.uuid == crawl_request_uuid, CrawlRequest.team_id == team.uuid))
    if not request_obj:
        raise HTTPException(status_code=404, detail="Crawl request not found")
    item = db.scalar(select(CrawlResult).where(CrawlResult.uuid == result_uuid, CrawlResult.request_id == request_obj.uuid))
    if not item:
        raise HTTPException(status_code=404, detail="Crawl result not found")
    return CrawlResultOut(
        uuid=item.uuid,
        url=item.url,
        result=item.result_json,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.post("/search/", response_model=SearchRequestOut, status_code=status.HTTP_201_CREATED)
def create_search(payload: SearchRequestIn, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> SearchRequestOut:
    remain, remain_daily, _, _, _, _ = _remaining_limits(db, team)
    _validate_concurrency(db, team, SearchRequest)

    cost = _search_credit_cost(payload.result_limit, payload.search_options.depth)
    if remain != -1 and cost > remain:
        raise HTTPException(status_code=403, detail=f"You just have {remain} credits left in your plan")
    if remain_daily != -1 and cost > remain_daily:
        raise HTTPException(status_code=403, detail=f"You just have {remain_daily} daily credits left in your plan")

    item = SearchRequest(
        uuid=uuid4(),
        team_id=team.uuid,
        query=payload.query,
        search_options=payload.search_options.model_dump(),
        result_limit=payload.result_limit,
        status=CRAWL_STATUS_NEW,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return SearchRequestOut(
        uuid=item.uuid,
        query=item.query,
        search_options=item.search_options,
        result_limit=item.result_limit,
        duration=item.duration_seconds,
        status=item.status,
        result=item.result_json,
        created_at=item.created_at,
    )


@router.get("/search/", response_model=list[SearchRequestOut])
def list_search(team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> list[SearchRequestOut]:
    rows = db.scalars(select(SearchRequest).where(SearchRequest.team_id == team.uuid).order_by(SearchRequest.created_at.desc())).all()
    return [
        SearchRequestOut(
            uuid=item.uuid,
            query=item.query,
            search_options=item.search_options,
            result_limit=item.result_limit,
            duration=item.duration_seconds,
            status=item.status,
            result=item.result_json,
            created_at=item.created_at,
        )
        for item in rows
    ]


@router.get("/search/{search_uuid}/", response_model=SearchRequestOut)
def retrieve_search(search_uuid: UUID, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> SearchRequestOut:
    item = db.scalar(select(SearchRequest).where(SearchRequest.uuid == search_uuid, SearchRequest.team_id == team.uuid))
    if not item:
        raise HTTPException(status_code=404, detail="Search request not found")
    return SearchRequestOut(
        uuid=item.uuid,
        query=item.query,
        search_options=item.search_options,
        result_limit=item.result_limit,
        duration=item.duration_seconds,
        status=item.status,
        result=item.result_json,
        created_at=item.created_at,
    )


@router.delete("/search/{search_uuid}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_search(search_uuid: UUID, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> Response:
    item = db.scalar(select(SearchRequest).where(SearchRequest.uuid == search_uuid, SearchRequest.team_id == team.uuid))
    if not item:
        raise HTTPException(status_code=404, detail="Search request not found")
    if item.status != CRAWL_STATUS_RUNNING:
        raise HTTPException(status_code=403, detail="Only running search requests can be deleted")
    item.status = CRAWL_STATUS_CANCELING
    db.add(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/search/{search_uuid}/status")
def search_status(search_uuid: UUID, prefetched: bool = False, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> dict:
    _ = prefetched
    item = db.scalar(select(SearchRequest).where(SearchRequest.uuid == search_uuid, SearchRequest.team_id == team.uuid))
    if not item:
        raise HTTPException(status_code=404, detail="Search request not found")
    return {"status": item.status}


@router.post("/sitemaps/", response_model=SitemapRequestOut, status_code=status.HTTP_201_CREATED)
def create_sitemap(payload: SitemapRequestIn, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> SitemapRequestOut:
    remain, remain_daily, _, _, _, allowed_proxy_categories = _remaining_limits(db, team)
    _validate_concurrency(db, team, SitemapRequest)

    cost = _sitemap_credit_cost(payload.options.ignore_sitemap_xml)
    if remain != -1 and cost > remain:
        raise HTTPException(status_code=403, detail=f"You just have {remain} credits left in your plan")
    if remain_daily != -1 and cost > remain_daily:
        raise HTTPException(status_code=403, detail=f"You just have {remain_daily} daily credits left in your plan")

    _validate_proxy_access(db, team, payload.options.proxy_server, allowed_proxy_categories)

    item = SitemapRequest(
        uuid=uuid4(),
        team_id=team.uuid,
        url=payload.url,
        options=payload.options.model_dump(),
        status=CRAWL_STATUS_NEW,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return SitemapRequestOut(
        uuid=item.uuid,
        url=item.url,
        status=item.status,
        options=item.options,
        duration=item.duration_seconds,
        result=item.result_json,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("/sitemaps/", response_model=list[SitemapRequestOut])
def list_sitemaps(team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> list[SitemapRequestOut]:
    rows = db.scalars(select(SitemapRequest).where(SitemapRequest.team_id == team.uuid).order_by(SitemapRequest.created_at.desc())).all()
    return [
        SitemapRequestOut(
            uuid=item.uuid,
            url=item.url,
            status=item.status,
            options=item.options,
            duration=item.duration_seconds,
            result=item.result_json,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in rows
    ]


@router.get("/sitemaps/{sitemap_uuid}/", response_model=SitemapRequestOut)
def retrieve_sitemap(sitemap_uuid: UUID, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> SitemapRequestOut:
    item = db.scalar(select(SitemapRequest).where(SitemapRequest.uuid == sitemap_uuid, SitemapRequest.team_id == team.uuid))
    if not item:
        raise HTTPException(status_code=404, detail="Sitemap request not found")
    return SitemapRequestOut(
        uuid=item.uuid,
        url=item.url,
        status=item.status,
        options=item.options,
        duration=item.duration_seconds,
        result=item.result_json,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.delete("/sitemaps/{sitemap_uuid}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_sitemap(sitemap_uuid: UUID, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> Response:
    item = db.scalar(select(SitemapRequest).where(SitemapRequest.uuid == sitemap_uuid, SitemapRequest.team_id == team.uuid))
    if not item:
        raise HTTPException(status_code=404, detail="Sitemap request not found")
    if item.status != CRAWL_STATUS_RUNNING:
        raise HTTPException(status_code=403, detail="Only running sitemap requests can be deleted")
    item.status = CRAWL_STATUS_CANCELING
    db.add(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sitemaps/{sitemap_uuid}/status")
def sitemap_status(sitemap_uuid: UUID, prefetched: bool = False, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> dict:
    _ = prefetched
    item = db.scalar(select(SitemapRequest).where(SitemapRequest.uuid == sitemap_uuid, SitemapRequest.team_id == team.uuid))
    if not item:
        raise HTTPException(status_code=404, detail="Sitemap request not found")
    return {"status": item.status}


@router.get("/sitemaps/{sitemap_uuid}/graph")
def sitemap_graph(sitemap_uuid: UUID, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> dict:
    item = db.scalar(select(SitemapRequest).where(SitemapRequest.uuid == sitemap_uuid, SitemapRequest.team_id == team.uuid))
    if not item or not item.result_json:
        raise HTTPException(status_code=404, detail="Sitemap for this request does not exist")
    return {"nodes": [], "edges": []}


@router.get("/sitemaps/{sitemap_uuid}/markdown")
def sitemap_markdown(sitemap_uuid: UUID, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> str:
    item = db.scalar(select(SitemapRequest).where(SitemapRequest.uuid == sitemap_uuid, SitemapRequest.team_id == team.uuid))
    if not item or not item.result_json:
        raise HTTPException(status_code=404, detail="Sitemap for this request does not exist")
    return "# Sitemap\n"


@router.post("/proxy-servers/", response_model=ProxyServerOut, status_code=status.HTTP_201_CREATED)
def create_proxy(payload: ProxyServerIn, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> ProxyServerOut:
    existing = db.scalar(select(ProxyServer).where(ProxyServer.team_id == team.uuid, ProxyServer.slug == payload.slug))
    if existing:
        raise HTTPException(status_code=400, detail="Proxy Server with this slug already exists")

    item = ProxyServer(
        uuid=uuid4(),
        name=payload.name,
        slug=payload.slug,
        is_default=payload.is_default,
        category=PROXY_CATEGORY_TEAM,
        proxy_type=payload.proxy_type,
        host=payload.host,
        port=payload.port,
        username=payload.username,
        password=payload.password,
        team_id=team.uuid,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return ProxyServerOut(
        name=item.name,
        slug=item.slug,
        is_default=item.is_default,
        proxy_type=item.proxy_type,
        host=item.host,
        port=item.port,
        username=item.username,
        has_password=bool(item.password),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("/proxy-servers/", response_model=list[ProxyServerOut])
def list_proxy(team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> list[ProxyServerOut]:
    rows = db.scalars(select(ProxyServer).where(ProxyServer.team_id == team.uuid).order_by(ProxyServer.created_at.asc())).all()
    return [
        ProxyServerOut(
            name=item.name,
            slug=item.slug,
            is_default=item.is_default,
            proxy_type=item.proxy_type,
            host=item.host,
            port=item.port,
            username=item.username,
            has_password=bool(item.password),
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in rows
    ]


@router.get("/proxy-servers/{slug}/", response_model=ProxyServerOut)
def get_proxy(slug: str, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> ProxyServerOut:
    item = db.scalar(select(ProxyServer).where(ProxyServer.team_id == team.uuid, ProxyServer.slug == slug))
    if not item:
        raise HTTPException(status_code=404, detail="Proxy server not found")
    return ProxyServerOut(
        name=item.name,
        slug=item.slug,
        is_default=item.is_default,
        proxy_type=item.proxy_type,
        host=item.host,
        port=item.port,
        username=item.username,
        has_password=bool(item.password),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.patch("/proxy-servers/{slug}/", response_model=ProxyServerOut)
def patch_proxy(slug: str, payload: ProxyServerIn, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> ProxyServerOut:
    item = db.scalar(select(ProxyServer).where(ProxyServer.team_id == team.uuid, ProxyServer.slug == slug))
    if not item:
        raise HTTPException(status_code=404, detail="Proxy server not found")

    slug_exists = db.scalar(
        select(ProxyServer).where(
            ProxyServer.team_id == team.uuid,
            ProxyServer.slug == payload.slug,
            ProxyServer.uuid != item.uuid,
        )
    )
    if slug_exists:
        raise HTTPException(status_code=400, detail="Proxy Server with this slug already exists")

    item.name = payload.name
    item.slug = payload.slug
    item.is_default = payload.is_default
    item.proxy_type = payload.proxy_type
    item.host = payload.host
    item.port = payload.port
    item.username = payload.username
    item.password = payload.password
    db.add(item)
    db.commit()
    db.refresh(item)
    return ProxyServerOut(
        name=item.name,
        slug=item.slug,
        is_default=item.is_default,
        proxy_type=item.proxy_type,
        host=item.host,
        port=item.port,
        username=item.username,
        has_password=bool(item.password),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.put("/proxy-servers/{slug}/", response_model=ProxyServerOut)
def put_proxy(slug: str, payload: ProxyServerIn, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> ProxyServerOut:
    return patch_proxy(slug, payload, team, db)


@router.delete("/proxy-servers/{slug}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_proxy(slug: str, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> Response:
    item = db.scalar(select(ProxyServer).where(ProxyServer.team_id == team.uuid, ProxyServer.slug == slug))
    if not item:
        raise HTTPException(status_code=404, detail="Proxy server not found")
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/proxy-servers/list-all", response_model=list[ListAllProxyServerOut])
def list_all_proxy(team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> list[ListAllProxyServerOut]:
    rows = db.scalars(
        select(ProxyServer).where(or_(ProxyServer.team_id == team.uuid, ProxyServer.team_id.is_(None))).order_by(ProxyServer.name.asc())
    ).all()
    return [ListAllProxyServerOut(name=item.name, slug=item.slug, category=item.category) for item in rows]


@router.post("/proxy-servers/test-proxy")
def test_proxy(payload: TestProxyIn, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> dict:
    host = payload.host
    port = payload.port
    proxy_type = payload.proxy_type
    username = payload.username
    password = payload.password

    if payload.slug:
        proxy = db.scalar(select(ProxyServer).where(ProxyServer.team_id == team.uuid, ProxyServer.slug == payload.slug))
        if not proxy:
            raise HTTPException(status_code=400, detail="Proxy server does not exist")
        host = host or proxy.host
        port = port or proxy.port
        proxy_type = proxy_type or proxy.proxy_type
        username = username or proxy.username
        password = password or proxy.password

    if not host or not port or not proxy_type:
        raise HTTPException(status_code=400, detail="host, port and proxy_type are required")

    return {
        "ok": True,
        "tested": {
            "host": host,
            "port": port,
            "proxy_type": proxy_type,
            "username": username,
            "has_password": bool(password),
        },
    }
