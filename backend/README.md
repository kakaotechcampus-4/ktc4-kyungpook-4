# Backend

예적금 금리 비교·포트폴리오 추천 서비스의 API 서버.

FastAPI + PostgreSQL 16 + Redis 7 / Python 3.13

---

## 시작하기

미리 깔아둘 것은 **Docker Desktop** 과 **[uv](https://docs.astral.sh/uv/)** 두 개뿐입니다.
Python 은 따로 안 깔아도 됩니다 — `.python-version` 을 보고 uv 가 알아서 받아옵니다.

```bash
brew install uv        # macOS. Windows 는 winget install astral-sh.uv
```

그다음 순서대로 실행하면 됩니다.

```bash
cd backend

docker compose up -d              # ① PostgreSQL + Redis 컨테이너
uv sync --frozen                  # ② .venv 생성 + 패키지 설치 (uv.lock 그대로)
cp .env.example .env              # ③ 설정 파일
uv run alembic upgrade head       # ④ DB 테이블 생성

uv run uvicorn app.main:app --reload    # 서버 실행
```

http://127.0.0.1:8000/docs 에서 Swagger 로 API 를 눌러볼 수 있습니다.

동작 확인:

```bash
curl localhost:8000/api/v1/health        # 서버
curl localhost:8000/api/v1/health/db     # DB 연결
curl localhost:8000/api/v1/health/redis  # Redis 연결
```

> **`uv run` 을 붙이는 이유**: 가상환경을 `source` 로 활성화하지 않아도 `.venv` 의 파이썬으로 실행됩니다.
> 활성화했다면 `uv run` 없이 `uvicorn app.main:app --reload` 로 써도 똑같습니다.
> VS Code 통합 터미널은 `.vscode/settings.json` 덕분에 자동으로 활성화됩니다.

## 자주 쓰는 명령

| 하려는 것 | 명령 |
|---|---|
| 서버 실행 (자동 재시작) | `uv run uvicorn app.main:app --reload` |
| 테스트 | `uv run pytest` |
| 린트 검사 (CI 와 동일) | `uv run ruff check . && uv run ruff format --check .` |
| 자동 수정 + 포맷 | `uv run ruff check . --fix && uv run ruff format .` |
| 마이그레이션 적용 | `uv run alembic upgrade head` |
| 마이그레이션 생성 | `uv run alembic revision --autogenerate -m "설명"` |
| 한 단계 되돌리기 | `uv run alembic downgrade -1` |
| DB 접속 | `docker exec -it ktc4-postgres psql -U ktc4 -d ktc4` |
| Redis 접속 | `docker exec -it ktc4-redis redis-cli` |
| 컨테이너 로그 | `docker compose logs -f` |
| 컨테이너 내리기 (데이터 유지) | `docker compose down` |
| DB 완전 초기화 (데이터 삭제) | `docker compose down -v && docker compose up -d` |

### 선택: Makefile 단축키

같은 명령을 짧게 쓰고 싶으면 `Makefile` 이 있습니다. **안 써도 무방합니다** — 위 명령을 그대로 치는 것과 결과가 같습니다.

```bash
make            # 전체 목록
make setup      # 위 ①~④ 를 한 번에
make run / test / lint / fmt / migrate / psql / redis
```

`make -n setup` 을 치면 실제로 어떤 명령이 실행되는지 볼 수 있습니다.

> Windows 에는 `make` 가 기본 설치돼 있지 않습니다. 위 표의 명령을 그대로 쓰거나 WSL 을 사용하세요.

## 폴더 구조

```
backend/
├── app/
│   ├── main.py        FastAPI 진입점
│   ├── core/          설정 (환경변수는 config.py 에서만 읽는다)
│   ├── db/            세션·Base·Redis 연결
│   ├── models/        SQLAlchemy 모델 = 테이블 정의
│   ├── schemas/       Pydantic 스키마 = API 입출력 (아직 비어 있음)
│   └── api/v1/        라우터
├── alembic/versions/  마이그레이션 이력
├── db/schema.sql      전체 스키마를 한눈에 보는 문서
└── tests/
```

### models / schemas 가 헷갈릴 때

같은 "스키마"라는 말이 세 군데서 다르게 쓰입니다.

```
HTTP 요청 JSON
   ↓  app/schemas/   Pydantic   "들어온 값이 말이 되나?"     → 아니면 422
   ↓  app/models/    SQLAlchemy "파이썬 객체 ↔ 테이블 행"
   ↓  db/schema.sql  DDL        "DB 가 물리적으로 강제"      → 뚫리면 INSERT 거부
PostgreSQL
```

## DB 스키마를 바꿀 때

`app/models/` 를 고친 뒤 마이그레이션을 만듭니다.

```bash
uv run alembic revision --autogenerate -m "add product sale_end_date"
# alembic/versions/ 에 생긴 파일을 반드시 눈으로 확인할 것
uv run alembic upgrade head
```

`db/schema.sql` 도 같이 고쳐야 합니다. **한쪽만 고치면 테스트가 실패합니다** —
`tests/test_schema_sync.py` 가 둘을 대조해서 컬럼·타입·제약·인덱스·주석까지 전부 비교합니다.

### 왜 두 군데를 유지하나

`schema.sql` 은 전체 구조를 한 파일에서 읽기 위한 문서이고, 모델은 코드에서 쓰는 정의입니다.
어긋나는 순간 테스트가 잡아주므로 드리프트는 생기지 않습니다.

## 이 프로젝트의 규칙

**허용된 값은 `app/models/enums.py` 한 곳에만 적습니다.**
DB CHECK 제약, API 검증, LLM 프롬프트가 전부 이 목록을 가져다 씁니다.
문자열을 직접 타이핑하지 마세요 — `"적금"` 대신 `PRODUCT_TYPES` 를 씁니다.

**상품 배치는 `upsert` 로 돌립니다.**
`DELETE + INSERT` 로 갱신하면 사용자의 가입 이력(`user_holding`)이 물고 있는 링크가
매 배치마다 전부 끊깁니다. PK 가 전부 결정적으로 생성되는 문자열인 이유가 이것입니다.

**Redis 는 캐시 전용입니다.**
원본 데이터를 여기에만 두지 않습니다. 날아가도 DB 에 있어야 합니다.

## 환경변수

`.env.example` 을 복사해 쓰며, 기본값이 `docker-compose.yml` 과 맞춰져 있어
로컬에서는 고칠 것이 없습니다. `.env` 는 git 에 올라가지 않습니다.

## 테스트

```bash
uv run pytest
```

개발 DB(`ktc4`) 는 건드리지 않고 `ktc4_test` 를 따로 만들어 씁니다 (`tests/conftest.py` 가 자동 생성).
컨테이너가 안 떠 있으면 실패하지 않고 skip 됩니다.

## CI

`feature/* → develop` PR 에서 `backend/**` 가 바뀌면 자동으로 돕니다.
린트 → 포맷 확인 → 마이그레이션 적용 → **롤백 왕복** → 테스트.

로컬에서 아래가 통과하면 CI 도 통과합니다.

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
```
