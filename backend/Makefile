# 자주 쓰는 명령의 단축키 모음. **선택 사항이다.**
# README 에 적힌 명령을 그대로 쳐도 결과는 같다. 어떤 명령으로 펼쳐지는지 보려면 `make -n <타겟>`.
# Windows 에는 make 가 기본 설치돼 있지 않으니 README 의 명령을 쓰거나 WSL 을 쓴다.
.PHONY: help up down setup run test lint fmt migrate rollback revision psql redis logs reset

help:  ## 이 목록 보기
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

up:  ## DB·Redis 컨테이너 띄우기
	docker compose up -d

down:  ## 컨테이너 내리기 (데이터는 유지)
	docker compose down

setup: up  ## 처음 한 번: 환경 생성 + 의존성 설치 + 테이블 생성
	uv sync --frozen
	@test -f .env || cp .env.example .env
	uv run alembic upgrade head
	@echo "준비 완료. 'make run' 또는 'uv run uvicorn app.main:app --reload' 로 서버를 띄우세요."

run:  ## 개발 서버 (코드 고치면 자동 재시작)
	uv run uvicorn app.main:app --reload

test:  ## 테스트
	uv run pytest

lint:  ## 린트 검사 (CI 와 동일)
	uv run ruff check .
	uv run ruff format --check .

fmt:  ## 자동 수정 + 포맷
	uv run ruff check . --fix
	uv run ruff format .

migrate:  ## 마이그레이션 적용
	uv run alembic upgrade head

rollback:  ## 마이그레이션 한 단계 되돌리기
	uv run alembic downgrade -1

revision:  ## 모델 변경을 마이그레이션으로 생성 (예: make revision M="add x")
	uv run alembic revision --autogenerate -m "$(M)"

psql:  ## DB 접속
	docker exec -it ktc4-postgres psql -U ktc4 -d ktc4

redis:  ## Redis 접속
	docker exec -it ktc4-redis redis-cli

logs:  ## 컨테이너 로그
	docker compose logs -f

reset:  ## DB 를 완전히 초기화 (데이터 전부 삭제)
	docker compose down -v
	docker compose up -d
	@sleep 5
	uv run alembic upgrade head
