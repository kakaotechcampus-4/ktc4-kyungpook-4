"""비동기 DB 세션."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,  # 유휴 커넥션이 끊긴 뒤 첫 요청이 실패하는 것을 막는다
)

SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI 의존성 - 요청 하나당 세션 하나."""
    async with SessionLocal() as session:
        yield session
