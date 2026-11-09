# 프로젝트 개요

'안정형' — 사용자의 목돈·월 저축액·기간을 입력받아, 예금·적금 상품을 조합해
세후 실수령액 기준 최적 포트폴리오 3안(단순형/균형형/최대형)을 제시하고, 가입 후에는
만기 캘린더와 실시간 진행률로 저축 여정을 관리해주는 서비스.

## 기술 스택

- Frontend: Flutter (Dart), Riverpod(flutter_riverpod), go_router, http
- Backend: FastAPI (Python 3.13), SQLAlchemy 2.0(async) + Alembic, `uv`
- DB: PostgreSQL 16
- Cache: Redis 7 (캐시 + 로그인 state·refresh 토큰 저장. 날아가면 다시 로그인하면 되는 것만 둔다)
- 인증: 소셜 로그인(Google·Kakao. Naver 는 제외) — 2026-11 구현됨. 자세한 건 아래 "인증·게스트" 참고

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
      core/                 # config.py(환경변수·CORS), security.py(JWT 발급·검증, 인증 쿠키)
      db/                   # base.py, session.py, redis.py
      models/               # SQLAlchemy 모델 = 테이블 정의 (아래 "DB 스키마" 참고)
      schemas/              # Pydantic 요청/응답 모델 (profile, portfolio, calendar)
      services/             # portfolio.py(계산 엔진), conditions.py(우대조건 판정), tax.py,
                            #   auth.py·oauth.py(로그인), chatbot.py, roadmap.py 등
      api/deps.py           # 현재 사용자 판별(로그인 쿠키 → 게스트 쿠키 순), 소유권 확인
      api/v1/               # 라우터: health, auth, users, profiles, portfolios, products, manual_entries
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
  product_condition 4테이블로 적재하는 임포터: `app/importers/erd_import.py`.
  배포 때마다 서버에서 자동 실행된다(upsert — 산출물에서 사라진 행을 지우지는 않는다)
- 추천 이유(AI Summary)와 파생값(`extra_vs_baseline`, `new_banks` 등)은 `ai/src/summary.py`
  (`ktc4_ai.summary`)가 계산한다. BE 는 그 값을 응답에 그대로 쓴다
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

## 인증·게스트 (2026-11 구현)

- 소셜 로그인 흐름: FE 가 `/auth/{provider}/login` 으로 이동 → 소셜사 로그인 →
  `/auth/{provider}/callback` 에서 쿠키를 굽고 FE(`FRONTEND_URL`)로 돌려보낸다
- 토큰은 전부 **HttpOnly 쿠키**로만 오간다 (FE 코드는 값을 못 읽고, 브라우저가 자동으로 싣는다)
  - `access_token`(JWT, 30분) / `refresh_token`(랜덤, 14일, Redis 에 해시로 저장) /
    `guest_token`(JWT, 30일 — 로그인 안 한 사용자)
  - FE 는 401 을 받으면 `/auth/refresh` 를 한 번 부른다 (`refreshing_client.dart`)
- **요청 본문에 `user_id` 를 받지 않는다** — 누가 요청했는지는 쿠키로만 판단(`app/api/deps.py`
  `get_principal_optional`: 로그인 쿠키 → 게스트 쿠키 순). 본문으로 받으면 남의 기록에 접근 가능해짐
- 로그인도 게스트 쿠키도 없이 `POST /profiles` 를 부르면 익명 사용자를 만들고 게스트 쿠키를 굽는다
- **게스트 → 로그인 승계**: 로그인 콜백에서 게스트 쿠키가 있으면 프로필·포트폴리오·직접 기록을
  계정으로 옮기고 게스트를 지운다 (`services/auth.py` `adopt_guest`). 같은 브라우저에서만 해당
- **앱(안드로이드)**: 쿠키 대신 `Authorization: Bearer <토큰>` 헤더를 쓴다 (`deps.py` 가 헤더 → 쿠키 순으로 확인)
  - 게스트: `POST /auth/app/guest` 로 게스트 토큰을 받아 기기에 저장 → 헤더로 보낸다
  - 로그인: 외부 브라우저로 `/auth/{provider}/login?client=app&code_challenge=<PKCE>` →
    콜백이 `APP_REDIRECT_URI`(`safebrother://auth`)`?code=<일회용 코드>` 로 앱을 연다 →
    `POST /auth/app/token`(code + code_verifier + guest_token) 으로 토큰 JSON 을 받으며 게스트 기록도 승계
  - 토큰 갱신·로그아웃: `/auth/refresh`·`/auth/logout` 본문에 `refresh_token` 을 넣는다 (refresh 는 200 + JSON)
  - 소셜사 콘솔의 redirect URI 는 웹과 같다(서버 콜백). 앱 쪽 구현은 `feature/be-app-auth` PR 본문의 FE 가이드 참고
- 서버 비밀값: `JWT_SECRET`(첫 배포 때 자동 생성), `GOOGLE_*`·`KAKAO_*`(비우면 그 로그인은 503)
- 설정: `APP_REDIRECT_URI`(기본 `safebrother://auth`) — 요청값으로 받지 않고 설정으로만 정한다(코드 가로채기 방지)

## 현재 백엔드 API (`app/api/v1/`, 전부 `/api/v1` 아래)

- `auth`: `GET /{provider}/login`, `GET /{provider}/callback`, `POST /refresh`, `POST /logout`,
  `POST /app/guest`·`POST /app/token`(앱 전용)
- `users`: `GET /me`(로그인 필수), `GET /me/roadmap`, `GET /me/calendar`
- `profiles`: `POST ""`(STEP1~3 입력 저장), `POST /{id}/etc-questions`·`/{id}/etc-answers`(챗봇 '기타' 조건)
- `portfolios`: `POST /recommend`(4안 + 단일형, 우대조건 반영), `POST /reasons`(추천 이유만 따로),
  `POST ""`(추천안 확정 가입), `GET /{id}/calendar`
- `products`: `GET ""`(기관별 상품 목록), `manual-entries`: 캘린더 직접 기록 저장·조회·삭제
- 상품 기간이 1/3/6/12/24/36개월 등 고정 구간이라, 요청 기간과 정확히 같은 옵션이
  없으면 그 이하 중 가장 긴 기간으로 대체 매칭한다

## 프론트-백엔드 인터페이스 갭 (2026-11-05 기준)

FE 결과 화면이 `frontend/lib/services/portfolio_field_mocks.dart` 의 가짜 값을 아직 쓰고 있다.
"예시" 표시가 없어 실제 값으로 오인될 수 있다.

- 이미 BE 가 주고 있어 **FE 매핑만 바꾸면 되는 것**
  - `newAccountCount` ← `new_bank_count` (지금은 상품 개수를 그대로 보여줘서 틀림)
  - `conditionDescription` ← 상품별 `applied_conditions`
  - `amountDescription` ← `product_type` + `allocated_amount` + `interest_rate`
    (예금이면 원금, 적금이면 월 납입액)
- **데이터가 없어 숨기는 게 나은 것**
  - `detailUrl`: 상품 공식 페이지 URL 이 산출물에 없다(`product_condition.evidence_url` 은
    우대조건 있는 상품에만 있음). AI 팀 수집이 필요
  - `branchVisitCount`: `product_option.join_channel` 값이 산출물에서 비어 있어 믿을 수 없다
- 단일형 카드(`single_plan_card.dart`)는 `product_type` 으로 "예치"/"월 납입" 문구를 나눠야 함 (PR #57)

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
- 서버 DB 를 직접 수정할 때는 지우기 전에 대상과 생성 시각을 먼저 확인한다 (로그인 전에 만든 팀원 테스트 데이터가 게스트로 섞여 있다)
