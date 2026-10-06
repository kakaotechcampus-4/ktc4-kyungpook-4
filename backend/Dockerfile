FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.25 /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./
# dev 그룹까지 설치한다: alembic 이 쓰는 동기 드라이버 psycopg2 가 dev 그룹에 있다.
RUN uv sync --frozen --no-install-project

COPY . .

EXPOSE 8000

# 기동할 때마다 마이그레이션을 먼저 적용한다 (이미 최신이면 아무것도 안 함).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
