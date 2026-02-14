from fastapi import APIRouter

from app.api.v1 import common, core, plan, user


api_router = APIRouter()
api_router.include_router(common.router, prefix="/api/v1/common", tags=["Common"])
api_router.include_router(user.router, prefix="/api/v1/user", tags=["User"])
api_router.include_router(core.router, prefix="/api/v1/core", tags=["Core"])
api_router.include_router(plan.router, prefix="/api/v1/plan", tags=["Plan"])
