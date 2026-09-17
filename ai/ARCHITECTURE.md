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
- **G1~G4**: Verification 단계의 검증 게이트 이름(원문 대조, 정합성 검산 등).

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

| 파일 | 역할 |
| --- | --- |
| `config.py` | `.env`에서 API 키(`FSS_AUTH_KEY`, `OPENAI_API_KEY` 등) 로드. 민감정보는 여기서만 읽음 |
| `schemas/product.py` | finlife API 원본 응답 스키마 (정기예금/적금 공통정보 + 옵션) |
| `schemas/extraction.py` | LLM(Claude Sonnet 5)이 우대조건 원문을 구조화한 결과 스키마 |
| `discovery/__init__.py` | 공시 API 호출 + 커뮤니티 크롤링 (Discovery 단계) — 아직 스텁 |
| `extraction/__init__.py` | 약관 원문 → 우대조건 구조화, LLM 호출 지점 A — 아직 스텁 |
| `verification/__init__.py` | G1~G4 검증 게이트 — 아직 스텁 |

`discovery/`, `extraction/`, `verification/`은 현재 `__init__.py`에 역할 설명만 있는 빈 스텁이고, 실제 로직은 `scripts/` 안의 스크립트(특히 `extract_conditions_ai.py`, `build_erd_tables.py`)에 먼저 프로토타입으로 구현되어 있어요. 정식 모듈화는 아직 진행 전이에요.

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
| `check_mismatch_samples.py` | `ai_condition_cache.jsonl`에서 MISMATCH 건 원문+AI 추출 결과 나란히 출력 |
| `check_review_queue.py` | `logs/review_queue*.json` 내용 확인 |
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
| `extract_verify_cu_saving.py` | 신협 적금 우대조건 텍스트가 있는 1,086건 전체에 Extraction 시험 실행 |
| `test_extraction.py` | Extraction 출력 단건 테스트 |
| `test_extraction_verify.py` ★ | Extraction + G3 검산(공시 우대폭 대조) 실행. 불일치/실패는 `logs/review_queue.json`으로 격리 |
| `test_ml_api.py` | 엘리스 ML API 채팅 호출 자체가 되는지 확인(호출 A/B 각각) |
| `test_cu_sample.py` | 신협 샘플로 스키마 검증 + 기존 Extraction/G3 파이프라인 시험 가동 |

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
| `check_mismatch_v2.py` | 남은 MISMATCH를 만기(term)별로 재분석 |
| `inspect_fixtures.py` | `tests/fixtures/` 전체 파일을 훑어 크기/레코드 수/첫 레코드 키 요약 |
| `list_kfcc_products.py` | `kfcc_rates.jsonl`의 고유 상품명별 지점 수 집계 |
| `search_kfcc_conditions.py` | `tests/fixtures` 안에서 "우대/조건/가산" 등 키워드가 포함된 텍스트 검색 |

## tests/fixtures/ — 원본 데이터 스냅샷

API에서 받아온 원본 그대로 저장된 파일들(용량이 커서 대부분 git에는 안 올라갈 가능성이 높아요 — `.gitignore` 확인 권장). 신협/새마을금고 관련 4개(`cu_rate_compare.jsonl`, `kfcc_branches.json`, `kfcc_rates.jsonl`, `mg_dbanking_rates.jsonl`, `kfcc_central_conditions_raw.jsonl`)가 서비스 반영 대상이고, 나머지(`deposit_sample.json` 등 finlife 샘플, 농협/수협 관련은 없음 — 이 폴더에는 신협/새마을금고/finlife 것만 있음)는 스키마 검증용 샘플이에요.

## output/ — 최종 산출물

- `ai_condition_cache.jsonl`: AI Extraction 호출 결과 캐시(재호출 방지 + 검증 상태 기록)
- `erd/institution.jsonl`, `erd/product.jsonl`, `erd/product_option.jsonl`, `erd/product_condition.jsonl`: `build_erd_tables.py`가 만드는 최종 정규화 테이블. BE와 DB 스키마를 맞출 때 이 4개가 기준이 됨