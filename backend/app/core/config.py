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

    # 프론트가 아직 확정된 dev 서버 주소가 없어(Flutter web/모바일 겸용) 흔한 로컬 포트를 모아둔다.
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    # Redis 는 캐시 전용이다. 원본 데이터는 절대 여기에만 두지 않는다.
    # (추천 결과 캐시 / 공시 API 응답 / 크롤링 중복 체크 / 세션)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # 소셜 로그인. 비밀값은 .env 에만 둔다 (서버는 /opt/ktc4/shared/.env).
    JWT_SECRET: str = ""  # 비어 있으면 토큰을 발급하지 않는다
    ACCESS_TOKEN_MINUTES: int = 30
    REFRESH_TOKEN_DAYS: int = 14
    # 소셜사에 등록한 redirect_uri 를 이 주소로 조립한다. 등록값과 한 글자라도 다르면 소셜사가 거부한다.
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:8080"  # 로그인이 끝나면 돌려보낼 곳
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    KAKAO_CLIENT_ID: str = ""  # 카카오 REST API 키
    KAKAO_CLIENT_SECRET: str = ""

    @property
    def cookie_secure(self) -> bool:
        """로컬(http)만 Secure 를 뺀다. 서버는 HTTPS 라 항상 붙인다."""
        return self.ENV != "local"

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
