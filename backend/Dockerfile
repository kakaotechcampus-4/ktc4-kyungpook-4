# 빌드 컨텍스트는 레포 루트다 (deploy/docker-compose.yml 참고).
# backend 가 ../ai 를 경로 의존성(ktc4-ai)으로 쓰기 때문에, 이미지 안에서도
# /app(backend) 옆에 /ai 를 두어 같은 상대 경로가 성립하게 한다.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.25 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY ai/pyproject.toml /ai/pyproject.toml
COPY ai/src /ai/src

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
# dev 그룹까지 설치한다: alembic 이 쓰는 동기 드라이버 psycopg2 가 dev 그룹에 있다.
RUN uv sync --frozen --no-install-project

COPY backend/ ./

EXPOSE 8000

# 기동할 때마다 마이그레이션을 먼저 적용한다 (이미 최신이면 아무것도 안 함).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
