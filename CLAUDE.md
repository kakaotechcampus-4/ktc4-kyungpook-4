# 프로젝트 개요

'안정형' — 사용자의 목돈·월 저축액·기간을 입력받아, 예금·적금 상품을 조합해
세후 실수령액 기준 최적 포트폴리오 3안(단순형/균형형/최대형)을 제시하고, 가입 후에는
만기 캘린더와 실시간 진행률로 저축 여정을 관리해주는 서비스.

## 기술 스택

- Frontend: Flutter (Dart), Riverpod(flutter_riverpod), go_router, http
- Backend: FastAPI (Python 3.13), SQLAlchemy 2.0(async) + Alembic, `uv`
- DB: PostgreSQL 16
- Cache: Redis 7 (현재 캐시 전용. 로그인/세션 관련 용도는 아직 미구현)
- 인증: 소셜 로그인(Google/Kakao/Naver) 설계만 있고 미구현 — 지금은 프로필 생성 시
  `user_id` 없으면 익명 사용자를 자동 생성하는 임시 방식으로 동작

## 브랜치 전략 (2026-09-26 변경 — 중요)

**`feature/be-init` 이 BE 본진이다.** BE 작업은 전부 여기로 병합한다.

```
개인 작업 브랜치 → feature/be-init → develop → main
```

- 새 BE 브랜치를 팔 때는 `develop` 이 아니라 **`feature/be-init` 에서** 분기한다:
  ```bash
  git fetch origin
  git switch feature/be-init
  git pull
  git switch -c <새-브랜치명>
  ```
- `feature/be-init` 이 `develop` 보다 앞서 있는 게 정상 상태다(BE 변경이 먼저 쌓이고,
  주기적으로 `develop` 에 올라간다). 반대로 `develop` 이 `be-init` 보다 앞서 있으면
  안 되므로, 작업 시작 전에 두 브랜치가 어긋나 있지 않은지 확인한다.
- 폐기: `feature/be-importer`(→ 코드는 원격에 남아있으나 브랜치는 close),
  `feature/be-api`, `restore/be-api`, `feature/fpanel` 은 이미 develop/be-init 에
  전부 반영되어 있으므로 삭제해도 무방하다.
- `main` / `develop` + 기능별 `feature/*` 브랜치, PR로 merge. `backend/**` 변경이 있는
  PR은 `backend-ci.yml`이 자동으로 lint/format/마이그레이션/테스트를 검증한다.

## 레포 구조

```
repo-root/
  backend/
    app/
      main.py
      core/                 # 환경변수 설정 (config.py). CORS 설정 있음. JWT 는 아직 없음
      db/                   # base.py, session.py, redis.py
      models/               # SQLAlchemy 모델 = 테이블 정의 (아래 "DB 스키마" 참고)
      schemas/              # Pydantic 요청/응답 모델 (profile, portfolio, calendar)
      services/             # portfolio.py — 포트폴리오 계산 엔진
      api/v1/                # 라우터: health, profiles, portfolios
      tests/
    alembic/versions/       # 마이그레이션 이력 (autogenerate)
    db/schema.sql           # 전체 스키마 문서 (모델과 자동 대조됨, test_schema_sync.py)
    db/seed_sample.sql      # 개발용 시드 (AI 산출물 기반 실데이터 50건)
    docker-compose.yml      # 로컬 Postgres + Redis
    pyproject.toml / uv.lock
    Makefile                # make seed 로 시드 데이터 적재
  frontend/                 # Flutter 앱 (실제 동작함 — 더 이상 스캐폴드 단계 아님)
    lib/
      screens/               # splash, tutorial, input(STEP1~3), result, calendar 등
      providers/             # onboarding_provider, portfolio_provider, result_provider,
                              #   calendar_provider (전부 실제 API 연동됨, mock 아님)
      services/api_client.dart   # profiles/portfolios/calendar 호출 모음
      models/                # PortfolioOption/Product, CalendarEvent 등
  ai/                        # 공시 연동 파이프라인 + 산출물
    scripts/                 # build_erd_tables.py, extract_conditions_ai.py 등
    output/erd/              # institution/product/product_option/product_condition.jsonl
                              # (실 데이터, 레포에 커밋되어 있음 — 대용량 주의)
  README.md
  CLAUDE.md
```

## DB 스키마 (15개 테이블 — `feature/be-init` 기준)

**2026-09-27 큰 변경**: 커뮤니티 특판을 크롤링·검증해 상품으로 승격시키는 파이프라인을
통째로 제거했다. 공시(금감원) 데이터만으로 상품을 전부 수집할 수 있게 되어 그 경로가
필요 없어졌기 때문이다. 이에 따라:

- **삭제된 테이블**: `special_offer`, `special_offer_option`, `crawl_history`,
  `institution_alias`
- `product.offer_id`, `product.source` 삭제 (모든 상품이 `OFFICIAL` 이라 source 자체가
  무의미해짐)
- `batch_type` 에서 `CRAWL`/`VERIFY` 제거
- `product_condition.verification_status` 는 남아있지만 **의미가 다르다** — 특판 검증이
  아니라 "AI 가 추출한 우대조건이 약관 원문과 맞는가"를 뜻한다
- `institution_type` 에 `새마을금고` 추가 (실측 1,039개 기관)
- `institution.name` 의 UNIQUE 제약 제거 — 지역이 다른 동명 기관이 실제로 존재함
  (예: "우리새마을금고 본점" 8곳)
- `product_option.join_channel` 신설, UNIQUE 구성 4→5 컬럼 — 같은 상품이라도 창구/비대면
  금리가 다른 경우가 있어(실측 758건) 채널을 옵션 단위로 내림
- `product_condition.rate_bonus` NULL 허용 — 원문에 우대폭 수치가 없는 조건(421건)을
  0으로 채우면 "가산 0%p"와 구별이 안 되는 문제 때문
- `CONDITION_TYPES` 어휘 9종 → 11종 (`공제가입`, `연령조건` 추가). 다만 `기타`가
  56.7%(25,118/44,285건)라 매칭에 실제로 쓸 수 있는 건 아직 절반이 안 됨

## 팀 구조 및 담당 경계

- **AI 팀**: 금감원 공시 API 연동, 우대조건 원문 파싱/AI 추출, 산출물(jsonl) 생성
- **백엔드 팀**: 인증, 사용자 프로필, 포트폴리오 계산, 캘린더/진행률, DB 스키마 관리
- **프론트 팀**: STEP1~3 입력, 결과 화면(포트폴리오 카드/상세), 캘린더 화면

## AI ↔ 백엔드 인터페이스

- AI 팀 산출물(`ai/output/erd/*.jsonl`)을 institution/product/product_option/
  product_condition 4테이블로 적재하는 실제 임포터가 있다
  (`feature/be-importer`에서 작업됐고, 코드는 원격에 남아 있음 — 브랜치 자체는 close됨.
  현재 개발은 `db/seed_sample.sql` 로 대체 중이니 실제 임포터 연결 필요 여부 확인할 것)
- 특판 검증 파이프라인이 사라졌으므로, 계산 엔진은 그냥 `product` 테이블만 조회하면
  자동으로 공시 검증된 상품만 보게 된다 (더 이상 별도 필터링 로직 불필요)
- **미해결 요청 (AI 팀 → BE, 2026-09-20 PR #6 에서 제기)**: `product_condition` 에
  적용 기간 상하한(`min_term_months`/`max_term_months`)이 없어, 1개월 상품 행에도
  "6~12개월제" 조건이 같이 붙어 오는 경우가 있음(확인 172건) — 그대로 계산하면 실제로
  못 받는 우대금리까지 더해지는 버그. `ai_condition_cache.jsonl` 에는 값이 있으니 최종
  출력에 포함해달라는 요청이 아직 처리 안 됨

## 설계 원칙

- "틀린 숫자를 보여주느니 덜 보여준다" — 불확실한 데이터는 계산에서 제외
- 급여이체·카드실적처럼 배타적으로만 적용 가능한 우대조건은 `exclusive_group` 으로
  묶어 한 상품에만 적용되도록 계산 (`product_condition.exclusive_group`)
- 사용자 프로필(`user_profile`)은 조회할 때마다 새 행 생성 — 이력 추적/재현성 확보
- 가입 보유내역(`user_holding`)은 가입 시점 금리·기관명을 스냅샷으로 저장
- 허용된 값(enum)은 `app/models/enums.py` 한 곳에만 적는다
- 상품(`product`, `product_option`)은 DELETE+INSERT 가 아니라 **upsert** 로 갱신 —
  안 그러면 `user_holding` 이 물고 있는 링크가 배치마다 끊김

## 현재 백엔드 API (`app/api/v1/`)

- `POST /api/v1/profiles` — STEP1 입력 저장 (`user_id` 없으면 익명 사용자 자동 생성)
- `POST /api/v1/portfolios/recommend` — 예금/적금 `base_rate` 기준 3안 추천
  (**우대조건 미반영** — `product_condition` 아직 계산에 안 붙음)
- `POST /api/v1/portfolios` — 추천안 확정 가입 (`user_portfolio`/`user_holding` 생성)
- `GET /api/v1/portfolios/{id}/calendar` — 납입/만기 일정
- 상품 기간이 1/3/6/12/24/36개월 등 고정 구간이라, 요청 기간과 정확히 같은 옵션이
  없으면 그 이하 중 가장 긴 기간으로 대체 매칭한다

## 프론트-백엔드 인터페이스 갭 (미해결)

프론트가 결과 화면(`PortfolioDetailScreen` 등)을 만들면서 아직 백엔드가 안 주는
필드를 모델에 미리 만들어두고 TODO 로 표시해뒀다 (`frontend/lib/models/portfolio_option.dart`):

- `PortfolioProduct.amountDescription`, `conditionDescription`, `detailUrl`(상품 공식
  안내 페이지 링크)
- `PortfolioOption.vsSingleDiff`(단일안 대비 세후 이자 차액), `newAccountCount`,
  `branchVisitCount`

지금은 빈 문자열/0 으로 채워져 있다 — 백엔드 스키마·API 응답에 이 값들을 추가하거나,
프론트와 논의해서 처리 방향을 정해야 한다.

## 로컬 개발 환경

```bash
# 백엔드
cd backend
docker compose up -d              # PostgreSQL + Redis
uv sync --frozen
cp .env.example .env
uv run alembic upgrade head
make seed                         # db/seed_sample.sql 적재 (선택)
uv run uvicorn app.main:app --reload

# 프론트
cd frontend
flutter pub get
flutter run
```

- 백엔드: http://localhost:8000 (API 문서: `/docs`)
- 헬스체크: `GET /api/v1/health`, `/health/db`, `/health/redis`
- CORS: 로컬 개발 포트(5173/3000/8080) 허용하도록 설정됨

## 배포 · 운영 (팀 EC2 서버)

- 서비스 주소: https://safebrother.duckdns.org (API 문서 `/docs`). 프론트(웹)와 API 가 같은 주소라 CORS 불필요
- **배포는 자동**: `develop` 에 push 되면 `.github/workflows/deploy.yml` 이 실행된다. Actions 탭에서 수동 실행도 가능
  - 흐름: Flutter 웹 빌드 → 번들(tar.gz) → S3 → SSM 으로 서버에서 `deploy/deploy.sh` 실행
  - 인증은 OIDC(`ktc-github-deploy` 역할). **액세스 키·SSH 키를 GitHub 에 넣지 않는다**
  - 배포할 때마다 기동 시 마이그레이션 적용 + AI 산출물 임포트(upsert)가 돈다
  - **실행 중 실패(마이그레이션 오류 등)는 자동 롤백되지 않는다.** 시연 직전엔 develop 머지를 멈춘다
- 서버 구성(`deploy/docker-compose.yml`): postgres · redis · backend · Caddy. 외부 포트는 80·443 만
  (보안 그룹은 운영진 템플릿 관리. **22번은 열지 않는다** — 접속은 SSM)
- 비밀값은 **서버의 `/opt/ktc4/shared/.env`(root 전용)에만** 있다. 레포·GitHub 에 없음
  - DB 비밀번호(첫 배포 때 자동 생성 — 바꾸면 기존 DB 볼륨에 못 붙는다), `SITE_ADDRESS`(HTTPS 도메인),
    `DUCKDNS_DOMAIN`·`DUCKDNS_TOKEN`(5분마다 IP 갱신), `OPENAI_API_KEY`·`OPENAI_BASE_URL`(비우면 AI Summary 대신 기본 문구)
  - 값을 바꾼 뒤에는 재배포해야 반영된다
- 서버 접속: 각자 PC 에 AWS SSO 프로필 + SSM 경유 SSH 설정(`ssh ktc-server`)이 필요하다. 설정 방법은 BE 담당에게 문의
  ```bash
  aws sso login --profile ktc4-team08          # SSO 만료 시
  ssh ktc-server 'cd /opt/ktc4/current/deploy && sudo docker compose ps'
  ssh ktc-server 'cd /opt/ktc4/current/deploy && sudo docker compose logs --tail 100 backend'
  ```
- 서버 DB 를 직접 수정할 때는 지우기 전에 대상과 생성 시각을 먼저 확인한다 (로그인이 없어 팀원 테스트 데이터도 게스트로 섞여 있다)
