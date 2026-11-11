# 안정형 — 테크스펙

> 작성 기준: `develop` 브랜치. 프로젝트 전반 맥락은 [CLAUDE.md](./CLAUDE.md) 참고.
> 본 문서는 요구사항 → 아키텍처 → 데이터모델 → 인터페이스 명세 → 릴리즈 순으로 구성한다.

---

## 1. 요구사항

### 1.1 기능 요구사항 (FR)

| ID | 요구사항 | 구현 위치 |
|---|---|---|
| FR-01 | 구글·카카오 소셜 로그인 (웹: 쿠키, 앱: Bearer+PKCE) | `auth.py`, `services/auth.py`, `services/oauth.py` |
| FR-02 | 로그인 없이 게스트로 서비스 이용(쿠키/앱 게스트 토큰), 이후 로그인 시 게스트 기록 승계 | `services/auth.py:adopt_guest` |
| FR-03 | STEP1~3 정보 입력(목돈·월저축액·기간, 보유은행·거주지·비과세 대상, 급여이체·카드사용액 등 우대조건 질문) 저장 | `POST /profiles` |
| FR-04 | 세후 실수령액 기준 포트폴리오 4종(단순형/균형형/최대형/안정형) + 단일형(주거래은행 비교 기준선) 추천 | `POST /portfolios/recommend`, `services/portfolio.py` |
| FR-05 | 추천 이유(AI 생성 자연어 설명)를 별도로 제공 (느린 연산 분리) | `POST /portfolios/reasons`, `ktc4_ai.summary` |
| FR-06 | AI가 판정하지 못한 '기타' 우대조건을 챗봇이 사용자에게 질문하고, 답변을 재반영해 재계산 | `POST /profiles/{id}/etc-questions`, `/etc-answers`, `services/chatbot.py` |
| FR-07 | 추천안 중 하나를 확정 가입(포트폴리오·보유상품·적용조건 영속화, 캘린더 이벤트 생성) | `POST /portfolios` |
| FR-08 | 가입 상품의 납입일·만기일 캘린더 표시, 2개월 이내 다가오는 일정만 노출(FE) | `GET /portfolios/{id}/calendar`, `GET /users/me/calendar` |
| FR-09 | 외부에서 가입한 상품을 캘린더에 직접 기록(생성/조회/삭제) | `manual_entries.py` |
| FR-10 | 경과 개월·누적 이자 등 저축 로드맵 제공 | `GET /users/me/roadmap`, `services/roadmap.py` |
| FR-11 | 기관별 상품 검색(신협·새마을금고는 지점 선택 필요) | `GET /products`, `GET /products/branches` |
| FR-12 | 화면 전반의 "OO님을 위한 포트폴리오" 등 사용자 이름 치환 | FE `userDisplayNameProvider` |

### 1.2 비기능 요구사항 (NFR)

| ID | 요구사항 | 근거/구현 |
|---|---|---|
| NFR-01 | **데이터 신뢰성 원칙** — 불확실한 값은 계산에서 제외한다("틀린 숫자를 보여주느니 덜 보여준다") | `services/conditions.py`, `services/onboarding.py` |
| NFR-02 | 배타적으로만 적용 가능한 우대조건(급여이체·카드실적 등)은 `exclusive_group`으로 묶어 한 상품에 최댓값 1건만 반영 | `product_condition.exclusive_group` |
| NFR-03 | 예금자보호 한도(기관당 1억원, 2025-09-01 상향 기준) 준수한 자동 분산 배분 | `services/portfolio.py:_allocate_greedy` |
| NFR-04 | LLM 호출 지점을 전체 시스템에서 정확히 3곳(챗봇 질문 생성 / 답변 해석 / 추천 이유 생성)으로 고정 — 숫자는 전부 결정론적 계산 엔진이 산출 | `ai/src/condition_qa.py`, `ai/src/summary.py` |
| NFR-05 | 인증 토큰은 Redis에 두되, 유실돼도 재로그인만 하면 되는 것만 저장(날아가도 안전) | CLAUDE.md "인증·게스트" |
| NFR-06 | 요청 본문으로 `user_id`를 받지 않음 — 신원 판별은 쿠키/헤더에서만(`get_principal_optional`) | `app/api/deps.py` |
| NFR-07 | 상품 데이터는 DELETE+INSERT가 아니라 upsert로 갱신(가입 보유내역이 참조하는 링크 보존) | `app/importers/erd_import.py` |
| NFR-08 | 주간 단위 데이터 신선도(금감원 공시·신협·새마을금고 1,039개 지점) — 매주 월요일 자동 수집 | `.github/workflows/weekly_pipeline.yml` |
| NFR-09 | 상품 수 급감(20% 이상) 시 자동 반영 중단 및 알림 | `ai/scripts/check_erd_drop.py` |
| NFR-10 | 동시 refresh 요청에도 로그아웃되지 않도록 30초 유예(grace) 구간을 둔 원자적 토큰 교체 | `services/auth.py:rotate_refresh` |
| NFR-11 | backend 변경 PR은 CI에서 lint/format/마이그레이션 왕복/테스트 자동 검증 | `.github/workflows/backend-ci.yml` |
| NFR-12 | 비밀값은 서버의 `.env`(root 전용)에만 존재, 레포·GitHub Actions에는 미노출(OIDC 인증) | `deploy/deploy.sh`, `.github/workflows/deploy.yml` |

### 1.3 범위 밖(Out of Scope, 현재 기준)

- 네이버 로그인(enum에는 존재하나 미구현)
- 상품 상세페이지 URL(`detailUrl`), 지점방문 횟수(`branchVisitCount`) — 원천 데이터 부재로 노출 보류
- CMA·ISA 등 비예적금 상품 (향후 계획 항목)

---

## 2. 아키텍처

### 2.1 전체 구성

```
┌──────────────────┐        HTTPS         ┌───────────────────────┐
│  Flutter 앱/웹    │ ───────────────────▶ │   FastAPI 백엔드        │
│  (FE)            │ ◀─────────────────── │   (safebrother...)     │
└──────────────────┘   쿠키 또는 Bearer    └───────────┬───────────┘
                                                        │
                                   ┌────────────────────┼────────────────────┐
                                   ▼                    ▼                    ▼
                           ┌───────────────┐   ┌────────────────┐   ┌────────────────┐
                           │ PostgreSQL 16 │   │   Redis 7      │   │ ktc4_ai 패키지  │
                           │ (영속 데이터)  │   │ (세션/캐시,    │   │ (LLM 3곳 호출: │
                           │               │   │  날아가도 무방) │   │ 질문생성/답변   │
                           └───────────────┘   └────────────────┘   │ 해석/추천이유)  │
                                                                     └────────────────┘
                                   ▲
                                   │ 배포 시 upsert 임포트 (erd_import.py)
                                   │
                           ┌───────────────────────────────────────┐
                           │ AI 파이프라인 (ai/)                     │
                           │ 금감원 공시 + 신협·새마을금고 전자공시   │
                           │  → LLM 구조화 추출 → ERD jsonl 산출물   │
                           │ (주 1회 GitHub Actions 자동 실행)        │
                           └───────────────────────────────────────┘
```

### 2.2 기술 스택

| 레이어 | 기술 | 버전 |
|---|---|---|
| Frontend | Flutter / Dart | SDK `^3.13.2`, 앱 버전 `1.0.0+1`, 배포 빌드 Flutter `3.47.5` |
| 상태관리 | flutter_riverpod | `^3.4.3` |
| 라우팅 | go_router | `^18.0.1` |
| HTTP | http | `^1.2.2` |
| 앱 인증 | flutter_secure_storage, flutter_web_auth_2, crypto | `^9.2.2`, `^4.1.0`, `^3.0.6` |
| Backend | FastAPI / Python | `>=3.13,<3.14`, fastapi `>=0.115`, uvicorn `>=0.30` |
| ORM | SQLAlchemy(async) + Alembic | `>=2.0`, `>=1.13` |
| DB 드라이버 | asyncpg(런타임) / psycopg2(마이그레이션·테스트) | `>=0.29` / `>=2.9` |
| 인증 토큰 | PyJWT | `>=2.15` |
| DB | PostgreSQL | 16 |
| Cache | Redis | 7 |
| AI | ktc4_ai 패키지(에디터블 로컬 의존성), Claude Sonnet 5 (`anthropic/claude-sonnet-5`) | — |
| 린트 | ruff (line-length 120, E/W/F/I/UP/B) | `>=0.6` |
| 테스트 | pytest, pytest-asyncio, fakeredis | `>=8.0` |
| 리버스 프록시 | Caddy 2 | — |
| 배포 인증 | AWS OIDC(`ktc-github-deploy` role) + SSM | — |

### 2.3 브랜치 전략

```
개인 작업 브랜치 → feature/be-init(BE 본진) → develop → main
```

- BE 작업은 `develop`이 아닌 `feature/be-init`에서 분기한다.
- `main`/`develop` + 기능별 `feature/*` 브랜치, PR로 머지.
- `develop`에 push되면 자동 배포(`deploy.yml`)된다 — 시연 직전에는 머지를 멈추는 것이 원칙.

### 2.4 배포 아키텍처 (팀 EC2 서버)

- 서비스 주소: `https://safebrother.duckdns.org` (프론트 웹·API 동일 주소, CORS 불필요)
- 배포 흐름: Flutter 웹 빌드(3.47.5) → tar.gz 번들(backend+deploy+ai output+frontend build) → S3 업로드 → SSM으로 EC2에서 `deploy/deploy.sh` 실행
- 서버 구성(`deploy/docker-compose.yml`): `postgres:16-alpine`, `redis:7-alpine`(AOF/RDB 끔), `backend`, `web`(Caddy — 정적 서빙 + `/api/*`·`/docs`·`/redoc`·`/openapi.json` 리버스 프록시 + SPA 폴백)
- 외부 포트는 80/443만 개방, 22번 미개방(SSM으로만 접속), 비밀값은 서버 `/opt/ktc4/shared/.env`(root 전용)에만 존재
- 배포 때마다: DB 마이그레이션 자동 적용 + AI 산출물(`ai/output/erd/*.jsonl`) upsert 임포트
- 실행 중 실패는 자동 롤백되지 않음(최근 릴리스 3개만 보관)

### 2.5 서비스 레이어 (`backend/app/services/`)

| 모듈 | 역할 |
|---|---|
| `conditions.py` | 티어(단순/균형/최대)별 우대조건 인정 범위 판정 + 실효금리 계산(배타그룹 최댓값 1건, 최고금리로 캡핑) |
| `portfolio.py` | 추천 엔진 본체 — 티어별 후보 상품 조회, 세후금리 정렬, 예금자보호 한도 내 탐욕적 분산 배분(`_allocate_greedy`), 기간 대체매칭, 확정 시 보유내역·캘린더 영속화 |
| `tax.py` | 이자소득세(일반 15.4%) + 신협·새마을금고 조합예탁금 비과세(3천만원 한도, 조특법 제89조의3) 계산 |
| `auth.py` | 소셜 로그인/게스트 계정 관리, state·PKCE코드·refresh토큰 Redis 관리, 게스트→로그인 승계, 동시요청 안전한 refresh 교체 |
| `oauth.py` | 구글·카카오 OAuth 어댑터(소셜사별 차이 흡수) |
| `chatbot.py` | '기타' 우대조건 질문 생성 + 답변 해석(충족/미충족/모름) + 저장 |
| `roadmap.py` | 가입 시점 확정금리 기준 경과기간·누적이자 계산(포트폴리오 확정 시 계산식과 동일 공식 재사용) |
| `onboarding.py` | STEP2·3 선택지 문구 ↔ DB 저장값 매핑 테이블(은행명→코드, 카드사용액 구간 등) |
| `products.py`(서비스) | 캘린더 직접기록용 기관별 상품/지점 목록 조회 |

---

## 3. 데이터모델

PostgreSQL 16, 전문: `backend/db/schema.sql` (15개 테이블). 제약조건 명명 규칙: `pk_/fk_/uq_/ck_/ix_`.

### 3.1 금융기관 마스터

**`institution`**
| 컬럼 | 타입 | 제약 |
|---|---|---|
| institution_code | varchar(20) | PK |
| name | varchar(100) | NOT NULL (UNIQUE 없음 — 동명 지역기관 존재) |
| institution_type | varchar(20) | NOT NULL, CHECK IN (은행, 저축은행, 신협, 새마을금고) |
| region | varchar(50) | nullable(전국구면 NULL) |
| is_active | boolean | NOT NULL DEFAULT true |

### 3.2 사용자 / 인증

**`app_user`**: `user_id`(PK), `nickname`, `email`(부분 UNIQUE 인덱스, nullable), `marketing_consent`(계정 단위 법적 기준값), `consent_updated_at`, `created_at`

**`social_account`**: `social_id`(PK), `user_id`→app_user(CASCADE), `provider`(CHECK: GOOGLE/KAKAO/NAVER — NAVER는 enum에만 존재), `provider_user_id`, `provider_email`, `linked_at` / UNIQUE(provider, provider_user_id), UNIQUE(user_id, provider)

### 3.3 조회 프로필 (조회 1건 = 1행, 이력 추적용)

**`user_profile`**: `profile_id`(PK), `user_id`→app_user, `capital`, `monthly_saving`, `period_months`(>0), `main_bank_code`→institution, `region`, `birth_date`, `salary_transfer`/`auto_transfer`/`savings_auto_transfer`/`pension_transfer`/`coop_insurance`/`app_install`(전부 nullable boolean, NULL=모름), `monthly_card_usage`, `marketing_consent`(조회 건별), `accepts_membership`, `coop_tax_eligible`, `coop_exempt_used`, `tax_exempt_used`, `answers`(jsonb, STEP2·3 원문 스냅샷), `created_at`
- CHECK: `period_months>0`, 금액 `>=0`, `capital>0 OR monthly_saving>0`

**`user_profile_bank`**: 보유은행 복수선택, UNIQUE(profile_id, institution_code)
**`user_profile_tax_exempt`**: `category` CHECK IN (65세이상, 장애인, 유공자, 기초생활수급자)
**`user_profile_social`**: `category` CHECK IN (다자녀, 한부모, 다문화, 신혼부부, 탈북자)
**`user_profile_extra`**: 챗봇 '기타' 조건 질의응답 — `condition_id`(FK 의도적 미설정, ERD 재임포트 대비), `condition_type`, `question_text`, `answer_value`, `raw_answer`, `answered_at` / CHECK(`answer_value IS NULL OR answered_at IS NOT NULL`), UNIQUE(profile_id, condition_id)

### 3.4 배치

**`batch_run`**: `run_id`(PK), `batch_type`(COLLECT/PARSE/MATURITY), `status`(RUNNING/SUCCESS/FAILED/PARTIAL, 기본 RUNNING), `started_at`/`finished_at`, `processed_count`/`failed_count`, `error_message` / CHECK: 종료상태면 finished_at 필수

### 3.5 상품 / 옵션 / 우대조건

**`product`**: `product_id`(varchar(64) PK, 기관코드+상품코드+상품명해시 결정적 생성), `run_id`→batch_run, `institution_code`→institution, `product_name`, `product_type`(예금/적금/예탁금), `amount_min/cap`, `monthly_min/cap`(적금만), `terms_text`, `region`, `membership_required`, `new_customer_only`, `min_age/max_age`, `parse_status`(PENDING/PARSED/FAILED), `snapshot_date`, `sale_end_date`, `is_active`
- 2026-09-27 삭제됨: `offer_id`, `source` 컬럼(특판 파이프라인 제거로 무의미해짐)

**`product_option`**(추천 엔진이 실제로 고르는 단위): `option_id`(PK), `product_id`→product(CASCADE), `period_months`(>0), `rate_type`(단리/복리), `reserve_type`(해당없음/정액적립식/자유적립식), `join_channel`(비대면/영업점/전체 — 758건 채널별 금리차 반영해 2026-09-27 신설), `base_rate`/`max_rate`(CHECK base≤max) / UNIQUE(product_id, period_months, rate_type, reserve_type, join_channel)

**`product_condition`**: `condition_id`(PK, 내용 해시 — condition_type은 키에서 제외), `product_id`→product(CASCADE), `condition_type`(11종, 3.7 참고), `rate_bonus`(NULL 허용 — 원문에 수치 없는 조건 421건 실측), `threshold_value`/`threshold_unit`(짝 제약), `applies_period_min/max`, `exclusive_group`, `evidence_text`/`evidence_url`, `verification_status`(EXACT/MISSING/EXCESS — AI추출 vs 약관원문 대조 의미), `confidence_badge`(확인됨/검수대기)

### 3.6 포트폴리오 / 보유

**`user_portfolio`**: `portfolio_id`(PK), `user_id`→app_user(CASCADE), `profile_id`→user_profile(RESTRICT, 계산근거 보존), `portfolio_type`(단순형/균형형/최대형/안정형 — 단일형은 비교 기준선이라 미저장), `goal_amount`/`goal_date`, `after_tax_total`, `status`(진행중/완료), `created_at`/`closed_at`(CHECK: closed_at 있으면 status=완료)

**`user_holding`**: `holding_id`(PK), `portfolio_id`→user_portfolio(CASCADE), `option_id`→product_option(SET NULL), `institution`/`product_name`(가입시점 스냅샷), `amount`/`monthly_amount`(둘 중 하나 필수), `base_rate`/`effective_rate`/`max_rate`(CHECK base≤effective≤max), `start_date`, `maturity_date`, `status`(유지중/만기)

**`user_holding_condition`**: `holding_id`→user_holding(CASCADE), `condition_id`→product_condition(SET NULL, 원본 삭제돼도 스냅샷 유지), `condition_type`, `rate_bonus`(>=0), `evidence_text` / UNIQUE(holding_id, condition_type)

**`user_manual_entry`**(캘린더 직접기록, 추천/가입과 별개): `entry_id`(PK), `user_id`→app_user(CASCADE), `entry_date`, `institution_name`, `product_id`→product(SET NULL, nullable), `product_name`, `amount`(>0), `memo`, `created_at`

### 3.7 Enum 전체 목록 (`backend/app/models/enums.py`)

| 상수 | 값 |
|---|---|
| INSTITUTION_TYPES | 은행, 저축은행, 신협, 새마을금고 |
| PRODUCT_TYPES | 예금, 적금, 예탁금 |
| SOCIAL_PROVIDERS | GOOGLE, KAKAO, NAVER(미구현) |
| SOCIAL_CARE_CATEGORIES | 다자녀, 한부모, 다문화, 신혼부부, 탈북자 |
| TAX_EXEMPT_CATEGORIES | 65세이상, 장애인, 유공자, 기초생활수급자 |
| BATCH_TYPES | COLLECT, PARSE, MATURITY |
| BATCH_STATUSES | RUNNING, SUCCESS, FAILED, PARTIAL |
| JOIN_CHANNELS | 비대면, 영업점, 전체 |
| PARSE_STATUSES | PENDING, PARSED, FAILED |
| RATE_TYPES | 단리, 복리 |
| RESERVE_TYPES | 해당없음, 정액적립식, 자유적립식 |
| THRESHOLD_UNITS | KRW, COUNT, MONTH, WEEK, DAY, HOUR, AGE, SCORE, STEP |
| CONDITION_VERIFY_STATUSES | EXACT, MISSING, EXCESS |
| CONFIDENCE_BADGES | 확인됨, 검수대기 |
| CONDITION_TYPES (11종) | 급여이체, 자동이체, 신규고객, 카드실적, 마케팅동의, 공과금이체, 연금수령, 비대면가입, 공제가입, 연령조건, 주거래은행, 기타 |
| PORTFOLIO_TYPES | 단순형, 균형형, 최대형, 안정형 |
| PORTFOLIO_STATUSES | 진행중, 완료 |
| HOLDING_STATUSES | 유지중, 만기 |

### 3.8 마이그레이션 이력 (`backend/alembic/versions/`, 10개)

```
7e09bd091feb_initial_schema
→ b1c4e7a90f32_schema_v2
→ a4c7e1f05d22_user_profile_step23_answers
→ c3d8f2a61b07_drop_product_join_channel
→ c6d1e8f2a7b4_user_manual_entry
→ b8e3f1a6c4d2_user_profile_extra_condition_id
→ d5a9e3c17f40_condition_type_main_bank
→ d2f7a9c3e1b5_user_portfolio_closed_at
→ e7b2c4d8a913_user_profile_coop_tax
→ f3a1d6b29c58_portfolio_type_stable
```

### 3.9 AI 파이프라인 출력 스키마 (`ai/output/erd/*.jsonl`)

> ⚠️ jsonl 원본 스키마는 DB 스키마와 컬럼명·값 체계가 다르다. 변환 로직은 `backend/app/importers/erd_import.py` 한 곳에만 있다 (예: `apply_period_min`→`applies_period_min`, `exclusion_group`→`exclusive_group`, `거치식`→`해당없음`).

- `institution.jsonl`: institution_code, name, institution_type, region, is_active
- `product.jsonl`: product_id, offer_id(미사용), run_id, source(미사용), snapshot_date, institution_code, product_name, product_type, amount_min/cap, monthly_min/cap, terms_text, region, join_channel(원본값), membership_required, new_customer_only, min_age/max_age, parse_status, sale_end_date, is_active
- `product_option.jsonl`: option_id, product_id, period_months, rate_type, reserve_type(원본값: 거치식 등), base_rate, max_rate
- `product_condition.jsonl`: condition_id, product_id, condition_type, rate_bonus, threshold_value, threshold_unit(원문단위), apply_period_min/max, exclusion_group, evidence_text, evidence_url

---

## 4. 인터페이스 명세

Base path: `/api/v1`. 인증 판별 순서: 로그인 쿠키(또는 `Authorization: Bearer`) → 게스트 쿠키(또는 게스트 토큰) (`app/api/deps.py`).

### 4.1 `health` (인증 불필요)

| Method | Path | 설명 |
|---|---|---|
| GET | `/health` | 프로세스 생존 |
| GET | `/health/db` | DB 연결 확인 |
| GET | `/health/redis` | Redis 연결 확인 |

### 4.2 `auth` (prefix `/auth`)

| Method | Path | 인증 | Request | Response |
|---|---|---|---|---|
| GET | `/{provider}/login` | 불필요 | query: `next?`, `client?`(web\|app), `code_challenge?`(app 필수, PKCE S256) | 302 리다이렉트 |
| GET | `/{provider}/callback` | 불필요 | query: `code,state,error?`, cookie: `guest_token?` | 302 (웹: 쿠키 설정 / 앱: 커스텀스킴 리다이렉트) |
| POST | `/app/guest` | 불필요 | — | 201 `GuestTokenOut{guest_token}` |
| POST | `/app/token` | 불필요 | `AppTokenRequest{code, code_verifier, guest_token?}` | `TokenOut` |
| POST | `/refresh` | refresh 쿠키 또는 body | `RefreshRequest{refresh_token?}` | 웹: 204 / 앱: 200 + JSON |
| POST | `/logout` | 선택 | `RefreshRequest?` | 204 |

### 4.3 `users` (prefix `/users`)

| Method | Path | 인증 | Response |
|---|---|---|---|
| GET | `/me` | 로그인 필수 | `UserMeOut{user_id, nickname, email, is_guest, providers}` |
| GET | `/me/roadmap` | 로그인 또는 게스트 | `RoadmapOut` |
| GET | `/me/calendar` | 로그인 또는 게스트 | `list[CalendarEventOut]` |

### 4.4 `profiles` (prefix `/profiles`)

| Method | Path | 인증 | Request | Response |
|---|---|---|---|---|
| POST | `""` | 선택(없으면 게스트 생성) | `ProfileCreate` | 201 `ProfileOut` |
| POST | `/{profile_id}/etc-questions` | 로그인 또는 게스트 | — | `EtcQuestionsOut` |
| POST | `/{profile_id}/etc-answers` | 로그인 또는 게스트 | `EtcAnswersIn` | `EtcAnswersOut` |

**`ProfileCreate` 주요 필드**: `lump_sum:int=0`, `monthly_saving:int=0`, `period_months:int(>0)`, `current_banks:list[BankLabel]`, `main_bank:BankLabel?`, `birth_date:date?`, `salary_account_transferable/auto_transfer_movable/savings_auto_transfer_possible/pension_account_transferable/cooperative_insurance_join_status/marketing_consent/can_install_bank_app: YesNo?`, `monthly_card_spending:CardSpendingLabel?`, `tax_exempt_eligibility:list`, `special_household_types:list`, `cooperative_membership_status?`, `cooperative_join_choices:list`, `mutual_finance_tax_exempt_eligible?`, `mutual_finance_existing_amount:int?`, `additional_note:str?(≤2000)`

### 4.5 `portfolios` (prefix `/portfolios`, 전부 로그인 또는 게스트 필요)

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/recommend` | `{profile_id, with_reason:bool}` | `{options: PortfolioOptionOut[], baseline: BaselineOut?}` |
| POST | `/reasons` | `{profile_id}` | `{reasons: dict[tier, str]}` (약 26초 소요, 별도 분리) |
| POST | `""` | `{profile_id, tier}` | 201 `PortfolioOut` |
| GET | `/{portfolio_id}/calendar` | — | `list[CalendarEventOut]` |

**`PortfolioOptionOut`**: `tier, products:PortfolioProductOut[], after_tax_total:int, reason:str?, extra_vs_baseline:int?, extra_vs_simple:int?, new_bank_count:int, required_actions:list[str], tax_saving_won:int, over_comprehensive_tax:bool`

**`PortfolioProductOut`**: `institution_code, institution_name, product_name, product_type, term_months, base_rate, interest_rate, allocated_amount, after_tax_interest, applied_conditions:AppliedConditionOut[]`

**`BaselineOut`**(단일형): `institution_name, product_name, product_type, products(항상 1개), after_tax_total, exceeds_protection:bool, period_note:str?`

### 4.6 `products` (prefix `/products`, 인증 불필요)

| Method | Path | Query | Response |
|---|---|---|---|
| GET | `""` | `institution`(필수), `product_type?`, `branch?` | `ProductListOut` |
| GET | `/branches` | `institution`(신협\|새마을금고) | `BranchListOut` |

### 4.7 `manual-entries` (prefix `/manual-entries`, 전부 로그인 필수)

| Method | Path | Request/Query | Response |
|---|---|---|---|
| POST | `""` | `ManualEntryCreate` | 201 `ManualEntryOut` |
| GET | `""` | query: `start?, end?` | `list[ManualEntryOut]` |
| DELETE | `/{entry_id}` | — | 204 (본인 기록만) |

---

## 5. 릴리즈

### 5.1 버저닝 현황

- 별도 CHANGELOG, Git 태그 체계 **없음**
- 유일한 버전 표시: `frontend/pubspec.yaml`의 `version: 1.0.0+1`
- 변경 이력은 PR 단위로 추적(아래 5.3)

### 5.2 CI/CD 파이프라인 (`.github/workflows/`)

| 워크플로 | 트리거 | 요약 |
|---|---|---|
| `backend-ci.yml` | PR→develop(`backend/**`), push→develop | postgres16+redis7 서비스 컨테이너 → `uv sync --frozen` → ruff lint/format → alembic upgrade/downgrade 왕복 → pytest |
| `deploy.yml` | push→develop, 수동 실행 | Flutter 웹 빌드 → 번들 → S3 → SSM으로 서버 `deploy/deploy.sh` 실행 → 상태 폴링 |
| `weekly_pipeline.yml` | 매주 월 KST 10:00, 수동 실행(`skip_drop_check` 옵션) | AI 데이터 수집→추출→ERD 빌드→급감 감지(실패 시 커밋 중단) → 성공 시 `ai/output/` 자동 커밋·push, 실패 시 Discord 알림 |
| `convention-check.yml` | PR opened/reopened/ready_for_review → main | PR 컨벤션 안내(차단 아님) |
| `assign-mentor.yml` | PR opened/reopened/ready_for_review → main | 멘토 자동 리뷰어 지정 |
| `notify-discord.yml` | 리뷰 요청/제출 이벤트 → main | 팀 Discord 알림 |
| `oidc-test.yml` | 수동 실행 | AWS OIDC 역할 연결 확인용 |

### 5.3 PR 히스토리 주요 마일스톤

| 시기 | PR | 내용 |
|---|---|---|
| 2026-09-06~09-26 | #1~#13 | AI 파트 초기 구축(FSS 상품 스키마 검증, ERD 구조화, 우대조건 추출 파이프라인) |
| 2026-09-22~23 | #7, #9 | BE 프로필/포트폴리오 API 최초 구현 + FE 연동 |
| 2026-09-27~30 | #14, #20, #22 | **특판 파이프라인 전체 제거** + DB 스키마 2차 조정 (가장 큰 아키텍처 변경) |
| 2026-09-30 | #19 | AI ERD 산출물 임포터 최초 구현 |
| 2026-10-07~13 | #32, #39 | AI Summary(추천 이유) 패키지화, 4티어+단일형 구조 개편 |
| 2026-10-12 | #38 | 포트폴리오 4개 안 개편 + 우대조건·세금 반영 실수령액 계산(현 계산 엔진 토대) |
| 2026-10-29~11-04 | #45, #59 | 안정형(4번째 티어) 추가, 기간 매칭 수정 |
| 2026-10-29 | #46 | STEP2·3 답변 저장 및 우대금리 계산 반영 |
| 2026-11-03~04 | #51, #58 | 챗봇 '기타' 우대조건 질의응답 연결, '모름' 처리 방식 변경 |
| 2026-11-04~05 | #56, #76 | 소셜 로그인(구글·카카오) 추가 → 안드로이드 앱 로그인(Bearer+PKCE+게스트 승계) 확장 |
| 2026-11-05 | #70~#73 | 로드맵 실데이터 연결, 계정 단위 캘린더 유지, FE 토큰 자동 갱신 |
| 2026-11-09 | #86~#88 | 동시 refresh 로그아웃 버그 수정(30초 유예), 안드로이드 앱 로그인 완성 |
| 2026-11-11(최신) | #95~#97 | 특판우대이율 중복계산 버그 수정, 가입 가능 나이 필터링, 시연 전 완성도 보정 |

### 5.4 환경 설정

- `backend/.env.example` 기준 필수 변수: `ENV, DEBUG, POSTGRES_*, REDIS_*, OPENAI_API_KEY/BASE_URL, JWT_SECRET, ACCESS_TOKEN_MINUTES(30), REFRESH_TOKEN_DAYS(14), BACKEND_PUBLIC_URL, FRONTEND_URL, APP_REDIRECT_URI(safebrother://auth), GOOGLE_*, KAKAO_*`
- 비우면: `OPENAI_API_KEY/BASE_URL` 비움 → AI Summary 대신 기본 문구 / `GOOGLE_*`·`KAKAO_*` 비움 → 해당 로그인 503

### 5.5 알려진 이슈 / 향후 계획

- FE `portfolio_field_mocks.dart`에 일부 결과 화면 필드가 아직 목업값 — `detailUrl`/`branchVisitCount`는 원천 데이터 부재로 숨김 유지 상태
- (발표자료 기준) 1개월 내: 금감원 오픈 API 실데이터 전환, 골든셋 20건 검증, 사용자 10명 사용성 테스트
- 3개월 내: 특판 검증 파이프라인 정식화, 사용자 신고 기반 조건 DB 보정
- 6개월 내: 만기 재예치 알림, 신규 특판 알림, 마이데이터 연동 검토, CMA·ISA 등 상품 범위 확대
