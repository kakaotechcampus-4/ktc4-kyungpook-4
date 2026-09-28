"""테스트 공통 설정.

테스트는 개발용 DB(ktc4)를 건드리지 않는다. 별도의 ktc4_test DB 를 쓰고,
스키마 테스트는 그 DB 의 public 스키마를 통째로 지웠다 다시 만든다.
개발 중이던 데이터가 날아가면 안 되므로 이 분리는 반드시 지킨다.
"""

import os

import pytest
from sqlalchemy import create_engine, text

from app.core.config import settings

# 개발 DB 이름 뒤에 _test 를 붙인 것을 기본값으로 쓴다.
# CI 나 로컬에서 다른 DB 를 쓰고 싶으면 TEST_DATABASE_URL 로 덮어쓴다.
TEST_DB_NAME = f"{settings.POSTGRES_DB}_test"


def _default_test_url() -> str:
    return (
        f"postgresql+psycopg2://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{TEST_DB_NAME}"
    )


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """테스트 DB 주소. 없으면 만들어 준다."""
    url = os.environ.get("TEST_DATABASE_URL") or _default_test_url()

    # postgres 관리 DB 에 붙어 테스트 DB 존재 여부를 확인한다.
    admin_url = url.rsplit("/", 1)[0] + "/postgres"
    try:
        admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"),
                {"n": url.rsplit("/", 1)[1]},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.rsplit("/", 1)[1]}"'))
        admin.dispose()
    except Exception as exc:  # DB 가 안 떠 있으면 테스트를 건너뛴다
        pytest.skip(f"테스트 DB 에 접속할 수 없다 ({exc.__class__.__name__}). docker compose up -d 확인")

    return url
