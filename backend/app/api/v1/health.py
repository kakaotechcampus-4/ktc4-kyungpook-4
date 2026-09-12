"""헬스체크."""

from typing import Annotated

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.redis import get_redis
from app.db.session import get_session

router = APIRouter(tags=["health"])


@router.get("/health", summary="프로세스 살아있는지")
async def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.ENV}


@router.get("/health/db", summary="DB 연결까지 확인")
async def health_db(session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "db": "reachable"}


@router.get("/health/redis", summary="Redis 연결까지 확인")
async def health_redis(client: Annotated[Redis, Depends(get_redis)]) -> dict[str, str]:
    await client.ping()
    return {"status": "ok", "redis": "reachable"}
