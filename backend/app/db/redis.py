"""Redis 연결.

캐시 전용이다. 여기 있는 값은 언제든 날아갈 수 있다고 가정하고 쓴다.
원본은 항상 PostgreSQL 에 있어야 한다.
"""

from redis.asyncio import Redis, from_url

from app.core.config import settings

redis: Redis = from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True,  # bytes 대신 str 로 받는다
)


async def get_redis() -> Redis:
    """FastAPI 의존성. 커넥션 풀은 클라이언트가 알아서 관리한다."""
    return redis
