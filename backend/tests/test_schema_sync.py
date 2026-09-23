"""db/schema.sql 과 app.models 가 어긋나지 않았는지 확인한다.

스키마 정의가 두 군데(SQL 파일 / 파이썬 모델)에 있어서 손으로 고치다 보면 갈라진다.
이 테스트는 schema.sql 로 빈 DB 를 만든 뒤 모델과 대조해, 컬럼·타입·NULL 허용·
FK·UNIQUE·인덱스·주석 중 하나라도 다르면 그 차이를 그대로 출력하고 실패한다.

docker compose 가 떠 있으면 `pytest` 한 줄로 돈다. 테스트 DB 는 conftest 가 알아서 만든다.
DB 가 안 떠 있으면 skip 된다.
"""

import pathlib

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text

import app.models  # noqa: F401  - Base.metadata 를 채운다
from app.db.base import Base

SCHEMA_SQL = pathlib.Path(__file__).resolve().parents[1] / "db" / "schema.sql"


@pytest.fixture(scope="module")
def engine(test_database_url):
    eng = create_engine(test_database_url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text(SCHEMA_SQL.read_text()))
    return eng


def test_models_match_schema_sql(engine):
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], "schema.sql 과 app.models 가 어긋났다:\n" + "\n".join(f"  {d}" for d in diff)


def test_every_table_is_mapped(engine):
    """schema.sql 에만 있고 모델에는 없는 테이블을 잡는다."""
    with engine.connect() as conn:
        in_db = {
            r[0]
            for r in conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            )
        }
    assert in_db == set(Base.metadata.tables)
