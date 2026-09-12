"""애플리케이션 설정 - 환경변수는 여기서만 읽는다."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "ktc4-kyungpook-4 backend"
    API_V1_PREFIX: str = "/api/v1"
    ENV: str = "local"  # local | dev | prod
    DEBUG: bool = True

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "ktc4"
    POSTGRES_PASSWORD: str = "ktc4"
    POSTGRES_DB: str = "ktc4"

    # SQL 로그. 로컬 디버깅용이며 운영에서는 꺼둔다.
    DB_ECHO: bool = False

    # Redis 는 캐시 전용이다. 원본 데이터는 절대 여기에만 두지 않는다.
    # (추천 결과 캐시 / 공시 API 응답 / 크롤링 중복 체크 / 세션)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        """alembic 전용. 마이그레이션은 동기 드라이버로 돈다."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
