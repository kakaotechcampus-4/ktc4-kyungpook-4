"""FastAPI 진입점."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import health, portfolios, profiles
from app.core.config import settings
from app.db.redis import redis
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # 프로세스가 내려갈 때 커넥션을 정리한다. 안 하면 테스트에서 경고가 쌓인다.
    await engine.dispose()
    await redis.aclose()


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(profiles.router, prefix=settings.API_V1_PREFIX)
app.include_router(portfolios.router, prefix=settings.API_V1_PREFIX)
