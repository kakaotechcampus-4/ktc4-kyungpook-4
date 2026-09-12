"""alembic 실행 환경.

URL 과 모델 메타데이터를 app 쪽에서 그대로 가져온다.
설정이 두 군데로 갈라지지 않게 하려는 것이다.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401  - 이 import 가 있어야 Base.metadata 가 채워진다
from alembic import context
from app.core.config import settings
from app.db.base import Base

config = context.config
# 마이그레이션은 동기 드라이버(psycopg2)로 돈다. 앱 런타임은 asyncpg 를 쓴다.
config.set_main_option("sqlalchemy.url", settings.sync_database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # 컬럼 타입 변경도 잡는다
            compare_server_default=True,  # DEFAULT 값 변경도 잡는다
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
