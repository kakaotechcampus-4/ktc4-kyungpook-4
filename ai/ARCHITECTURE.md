# AI 파트 아키텍처 개요

> 이 문서는 `ai/` 폴더의 파일들을 열어보기 전에 먼저 읽는 지도용 문서예요.
> 무엇이 핵심 파이프라인이고 무엇이 일회성 조사/점검 스크립트인지 구분하는 게 목적입니다.
> 프로젝트 배경(요구사항, 설계 결정)은 `docs/architecture-decisions.md`와
> Claude 프로젝트의 `상호금융 데이터소스 조사` 문서를 참고하세요. 이 문서는 "파일이 뭘 하는지"에만 집중합니다.

## 한눈에 보는 용어

- **finlife**: 금융감독원(FSS) 공시 API. 은행/저축은행/신협 세 권역만 지원(`topFinGrpNo`로 구분).
- **CU**: 신협(신용협동조합). finlife에도 있지만, 더 상세한 자체 공시(`cu.co.kr`)를 별도로 수집.
- **KFCC / MG**: 새마을금고. finlife 대상이 아니라서 지점별 API를 직접 리버스엔지니어링해서 수집.
- **NH / 수협**: 조사 후 스코프 아웃(팀 결정). 관련 파일은 보존만 되어 있고 서비스에는 미반영.

## 폴더 구조

```
ai/
├── src/              핵심 재사용 모듈 (파이프라인 본체)
├── scripts/          데이터 수집·점검·검증·빌드용 실행 스크립트 (신협/새마을금고 교차검증 스크립트도 여기로 통합됨)
├── tests/fixtures/   API에서 받아온 원본 데이터 스냅샷 (대용량 json/jsonl)
├── output/           최종 산출물 (ERD 테이블 + AI 추출 캐시)
└── docs/             설계 결정 메모
```

## src/ — 파이프라인 본체

이 프로젝트의 "제품 코드"에 해당하는 부분. 나머지(scripts/, scripts_check/)는 전부 이 모듈들을 만들거나 검증하기 위한 보조 도구예요.

**패키지 배포**: `ai/pyproject.toml`이 이 `src/` 폴더를 `ktc4_ai`라는 이름의 파이썬 패키지로 배포해요. BE는 `backend/`에서 `uv add --editable ../ai`로 설치하고 `from ktc4_ai.summary import generate_summary`처럼 import 해요. 스크립트(`scripts/*.py`)는 기존처럼 `from src.xxx`로 쓰면 되고, 대신 `src/` 안의 모듈끼리는 **반드시 상대 import**(`from .config import ...`)를 써야 두 방식 모두에서 동작해요.

| 파일 | 역할 |
| --- | --- |
| `config.py` | `.env`에서 API 키(`FSS_AUTH_KEY`, `OPENAI_API_KEY` 등) 로드. 민감정보는 여기서만 읽음 |
| `schemas/product.py` | finlife API 원본 응답 스키마 (정기예금/적금 공통정보 + 옵션) |
| `schemas/extraction.py` | LLM(Claude Sonnet 5)이 우대조건 원문을 구조화한 결과 스키마 |
| `summary.py` | Summary(호출 B) 본체 - 포트폴리오 3개 티어의 reason 생성(`generate_summary`). 기존/신규 은행 구분, 단순형 대비 차액 등 파생값은 `_enrich_options()`에서 코드로 계산, 신협(`CU-`)·새마을금고(`KFCC-`)는 항상 신규 가입 처리. BE가 `ktc4_ai.summary`로 호출 |
| `schemas/summary.py` | Summary(호출 B) 결과 스키마 - 포트폴리오 3개 티어(단순형/균형형/최대형)별 추천 설명(reason) |
| `discovery/__init__.py` | 공시 API 호출 + 커뮤니티 크롤링 (Discovery 단계) — 아직 스텁 |
| `extraction/__init__.py` | 약관 원문 → 우대조건 구조화, LLM 호출 지점 A — 아직 스텁 |

`discovery/`, `extraction/`은 현재 `__init__.py`에 역할 설명만 있는 빈 스텁이고, 실제 로직은 `scripts/` 안의 스크립트(특히 `extract_conditions_ai.py`, `build_erd_tables.py`)에 먼저 프로토타입으로 구현되어 있어요. 정식 모듈화는 아직 진행 전이에요. (`verification/`은 수치 검증 로직 자체를 완전히 제거하기로 하면서 폴더째 삭제했어요 - 2026-09-30.)

## scripts/ — 목적별 그룹

50개 스크립트 대부분은 "한 번 실행하고 결과를 확인하는" 조사/점검용이에요. 실제로 반복 실행되는 핵심 파이프라인은 표 마지막의 ★ 표시 3개입니다.

### 1) 수집 (fetch_*)
소스별로 원본 데이터를 받아 `tests/fixtures/`에 저장.

| 파일 | 수집 대상 |
| --- | --- |
| `fetch_all_products.py` | finlife 전체(은행/저축은행/신협 × 정기예금/적금), 페이지네이션 포함 |
| `fetch_cu_rate_compare.py` | 신협 `cu.co.kr` 예금 금리비교 전자공시 (기본금리+대면/비대면+우대조건 원문) |
| `fetch_kfcc_branches.py` | 새마을금고 전국 지점 디렉토리 (1,039개) |
| `fetch_kfcc_rates.py` | 새마을금고 지점별 실제 상품/금리 (`fetch_kfcc_branches.py` 결과가 먼저 필요) |
| `fetch_kfcc_central_conditions.py` | 새마을금고 중앙 금융상품몰 상세설명(우대이율 텍스트) — 09-17 새로 추가된 소스 |

### 2) 탐색/스키마 확인 (peek_*)
API를 처음 뚫을 때 구조를 확인하던 일회성 스크립트. 발견 내용은 이미 스키마(`src/schemas/`)와 문서에 반영되어서, 목적이 겹쳤던 나머지(`find_cu_code.py`, `peek_fixtures2.py`, `peek_fixtures3.py`, `peek_bank_savingsbank.py`, `peek_mg_dbanking.py`, `scan_all_topfingrpno.py`, `check_topfingrpno.py`, `verify_cu_032000.py`)는 정리했어요.

`peek_fixtures.py` (tests/fixtures 확정 사용 데이터 4개 파일의 필드 구조 확인용, 남겨둠)

### 3) 데이터 품질 점검 (check_*)
| 파일 | 확인 내용 |
| --- | --- |
| `check_cu_bonus.py` | 신협에서 `spcl_cnd='없음'`인데 실제로는 우대폭(`intr_rate2 > intr_rate`)이 있는 모순 사례 |
| `check_cu_spcl_cnd.py` | 신협 `spcl_cnd` 필드 길이 분포 + 샘플 |
| `check_dash.py` | `kfcc_rates.jsonl`의 `"-"`/빈 문자열 등 비정상 금리 값 |
| `check_high_rates.py` | `cu_rate_compare.jsonl`에서 4% 이상 특판급 금리 탐지 |
| `check_template_reuse.py` | 서로 다른 기관인데 `spcl_cnd`가 완전히 동일한 "템플릿 재사용 의심" 사례 |
| `check_ai_errors.py` | `ai_condition_cache.jsonl`에서 AI 호출 실패 건 에러 메시지 집계 |
| `check_ai_usage.py` | `scripts/` 폴더 전체를 스캔해서 AI(LLM) 호출 사용 현황 파악 |
| `check_ml_api_models.py` | 엘리스 ML API에서 실제 사용 가능한 model_id 확인 |

### 4) 품질 검증 (validate_*)
| 파일 | 검증 대상 |
| --- | --- |
| `validate_cu_full.py` | 신협 전체 데이터(`deposit_cu_sample.json`, `saving_cu_sample.json`) |
| `validate_cu_rate_compare.py` | `cu_rate_compare.jsonl` 품질 |
| `validate_kfcc_rates.py` | `kfcc_rates.jsonl` 파싱 품질(1,039개 지점 × 2종) |
| `validate_schema.py` | 은행/저축은행 4개 조합 전체 스키마 검증 |

### 5) 진단 (diag*)
| 파일 | 진단 내용 |
| --- | --- |
| `diagnose_zero_rate.py` | `base_rate == 0%` 케이스 원인 |
| `diagnose_zero_rate_kfcc_finlife.py` | 위와 동일 문제를 새마을금고/finlife 쪽에서 별도 진단 |

(농협 전용 진단이던 `diag_nh.py`는 농협이 스코프 아웃되어 정리했어요.)

### 6) AI Extraction 파이프라인 ★핵심
| 파일 | 역할 |
| --- | --- |
| `extract_conditions_ai.py` ★ | 우대조건(`spcl_cnd`)을 Claude Sonnet 5 호출로 구조화하는 핵심 스크립트 (v3~v8) |
| `reextract_for_new_category.py` | condition_type 카테고리 확장 시 전체 재추출(`extract_conditions_ai.py --fresh`) + `build_erd_tables.py` 재빌드 + 재분류 전/후 비교 리포트를 한 번에 처리 (2026-09-30 추가) |
| `extract_verify_cu_saving.py` | 신협 적금 우대조건 텍스트가 있는 1,086건 전체에 Extraction 시험 실행 |
| `test_ml_api.py` | 엘리스 ML API 채팅 호출 자체가 되는지 확인(호출 A/B 각각) |

### 7) API 연결 테스트
`test_saving_api.py`(FSS 적금 API), `test_savingsbank_api.py`(저축은행 정기예금+적금)

### 8) 최종 산출물 빌드 ★핵심
| 파일 | 역할 |
| --- | --- |
| `build_erd_tables.py` ★ | 신협+새마을금고 원본 데이터를 `output/erd/*.jsonl`(institution/product/product_option/product_condition)로 변환하는 핵심 빌드 스크립트 |
| `patch_build_erd.py` | `build_erd_tables.py`의 `attach_ai_conditions()` 함수만 콕 집어 고치는 패치용 |
| `qa_erd_tables.py` | `build_erd_tables.py` 산출물 검수 |

### 9) 새마을금고 랭킹/파생 데이터
`rank_mg_dbanking.py`(MG더뱅킹 특판 랭킹 추출). (농협/수협 정찰 결과 요약이던 `summarize_recon.py`는 두 기관 모두 스코프 아웃되어 정리했어요.)

### 10) 소스 간 교차검증 (원래 scripts_check/, scripts/로 통합됨)

`scripts/check_*`가 "데이터 자체의 이상치"를 찾는 거라면, 이 그룹은 "두 소스(finlife vs cu.co.kr, kfcc 등) 간의 불일치"를 찾아요.

| 파일 | 역할 |
| --- | --- |
| `compare_cu_products.py` | finlife 신협 상품 수 vs 다른 소스 상품 수 비교(기관명 정규화 후) |
| `compare_cu_sources.py` | finlife 신협 기관명 목록과 다른 소스 기관명 목록 교차 대조 |
| `inspect_fixtures.py` | `tests/fixtures/` 전체 파일을 훑어 크기/레코드 수/첫 레코드 키 요약 |
| `list_kfcc_products.py` | `kfcc_rates.jsonl`의 고유 상품명별 지점 수 집계 |
| `search_kfcc_conditions.py` | `tests/fixtures` 안에서 "우대/조건/가산" 등 키워드가 포함된 텍스트 검색 |

### 11) Step3 챗봇 로직 / Summary 프롬프트 ★핵심

| 파일 | 역할 |
| --- | --- |
| `condition_qa.py` ★ | FR-04 미니플로우① - '기타' 조건 AI 질문 생성(호출 A-1) + 자유텍스트 답변 파싱(호출 A-2). 고정 10개 카테고리는 템플릿 질문(AI 미사용), 모든 불확실/실패 케이스는 `conservative_fallback()`로 "조건 미충족" 단일 처리 |
| `summary_prompt.py` ★ | Summary(호출 B) 로컬 품질 확인용 실행 스크립트. 본체는 `src/summary.py`로 이동. 손으로 만든 예시 포트폴리오로 AI 응답(3문단, 4~6문장)을 눈으로 확인. 숫자는 재계산하지 않고 인용만 함, AI 실패 시 `_fallback_reason()`으로 대체 |

NFR-04("LLM 호출 지점이 정확히 3곳") 대응: (A) `condition_qa.py`의 질문 생성, (B) `condition_qa.py`의 답변 파싱, (C) `src/summary.py`의 Summary - 3곳으로 고정. Summary는 티어마다 따로 호출하지 않고 3개 티어를 한 번에 묶어서 호출함(4번째 호출 지점이 생기는 걸 방지).

## tests/fixtures/ — 원본 데이터 스냅샷

API에서 받아온 원본 그대로 저장된 파일들(용량이 커서 대부분 git에는 안 올라갈 가능성이 높아요 — `.gitignore` 확인 권장). 신협/새마을금고 관련 4개(`cu_rate_compare.jsonl`, `kfcc_branches.json`, `kfcc_rates.jsonl`, `mg_dbanking_rates.jsonl`, `kfcc_central_conditions_raw.jsonl`)가 서비스 반영 대상이고, 나머지(`deposit_sample.json` 등 finlife 샘플, 농협/수협 관련은 없음 — 이 폴더에는 신협/새마을금고/finlife 것만 있음)는 스키마 검증용 샘플이에요.

## output/ — 최종 산출물

- `ai_condition_cache.jsonl`: AI Extraction 호출 결과 캐시(재호출 방지). v10부터 검증 상태(verification_status/confidence_badge) 필드는 제거됨
- `erd/institution.jsonl`, `erd/product.jsonl`, `erd/product_option.jsonl`, `erd/product_condition.jsonl`: `build_erd_tables.py`가 만드는 최종 정규화 테이블. BE와 DB 스키마를 맞출 때 이 4개가 기준이 됨

## condition_type 카테고리 확장 시 체크리스트

(2026-09-28, PR #11 리뷰 — junhee-ko: "새 condition_type 추가 시 어떤 계층까지 코드를
바꿔야 하는지" 코멘트에 대한 답으로 추가함)

새 카테고리(예: '주택청약보유') 하나를 추가할 때 거쳐야 하는 4단계:

1. **AI prompt/taxonomy** — `extract_conditions_ai.py`의 SYSTEM_PROMPT 카테고리 목록에
   추가.
2. **원문 전체 재추출** — `python scripts/reextract_for_new_category.py`를 실행하면
   `extract_conditions_ai.py --fresh`(전체 재추출) + `build_erd_tables.py`(재빌드) +
   재분류 전/후 비교 리포트까지 한 번에 처리됨(2026-09-30 추가, `--report-only`로
   재추출 없이 현재 상태만 확인도 가능). 참고로 평소 `extract_conditions_ai.py`를
   플래그 없이 그냥 실행하면 원문(spcl_cnd) 내용이 캐시와 달라진 상품만 자동으로
   재추출되므로(신규/변경 상품 자동 감지), `--fresh`(전체 재추출)는 카테고리 자체를
   새로 추가할 때만 쓰면 됨.
3. **BE `CONDITION_TYPES` enum + DB CHECK 제약** (`backend/app/models/enums.py`) — 새
   값 추가 + 필요 시 Alembic 마이그레이션. AI 쪽에서 목록만 늘리고 여기를 안 맞추면
   insert가 CHECK 제약에 걸려 실패함(실제로 PR #11에서 한 번 겪은 문제).
4. **BE의 조건 판정 로직** — 새 카테고리를 "정형 조건"(코드가 자동 판정)으로 다룰지,
   아니면 "기타"처럼 AI가 자연어 질문을 생성하는 대상으로 둘지는 AI 파트 혼자 못 정하고
   매번 BE와 상의해서 결정.

지금은 이 목록이 AI(`extract_conditions_ai.py`)와 BE(`enums.py`) 양쪽에 각각
하드코딩되어 있어서 어긋나기 쉬운 구조임 — 장기적으로 한 곳(공유 설정 파일 등)에서
관리하는 구조로 바꾸는 걸 검토 중(`claude/PR11_리뷰_후속조치_TODO_20260928.md` 참고).
