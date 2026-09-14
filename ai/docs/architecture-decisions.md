# AI 파트 아키텍처 결정 메모 (W4)

## 1. LLM 호출 지점 — 2곳으로 확정

- 호출 A (Extraction): 약관/공시 원문 텍스트 → 우대조건 구조화. **배치**로 실행, 사용자 세션과 무관.
- 호출 B (Summary): 계산 엔진이 산출한 배분안 3종 숫자 → 장단점 설명 문장. 세션당 1회, **실시간** 실행.
- STEP1~3, 챗봇 미니플로우(FR-04, FR-05)는 버튼/드롭다운/조건식 기반 규칙 처리 — LLM 호출 없음.
- 근거: 계산은 결정론적 코드가 맡아야 정확성이 보장되고, LLM은 텍스트 변환 역할에만 한정해야
  비결정성으로 인한 신뢰도 문제를 피할 수 있음.

## 2. 배치 vs 실시간 구조 — 경계 확정

- **배치**(주기 실행): Discovery(공시 API + 커뮤니티 크롤링) → Extraction(호출 A) →
  Verification(G1·G2·G3·G4) → DB 저장(product, product_condition, special_offer)
- **실시간**(사용자 요청 시): DB에서 후보 필터링 → 사용자 충족 조건 매칭(규칙 기반) →
  계산 엔진 → 배분안 3종 구성 → 요약(호출 B)
- 근거: 상품의 우대조건 텍스트는 사용자와 무관한 정보라 매 세션 재파싱하면
  레이턴시·비용·결과 비일관성 문제가 생김. 한 번 검증해서 저장해두면
  NFR-03(3초 이내 첫 이벤트)도, "같은 상품은 항상 같은 결과"라는 신뢰도도 같이 확보됨.
- 참고: "실시간"의 의미는 (파싱까지 포함한 전체를 매번 다시 한다)가 아니라
  (사용자 맞춤 연산만 매번 한다)는 뜻으로 재정의함.

## 3. 배치 재실행 주기

- 공시 상품: 재파싱(Extraction)은 실제 발행 주기(주 1회)에 맞춤. API 호출/캐싱 자체는
  장애 대비용으로 더 자주 해도 무방(비용 거의 안 듦).
- 특판(커뮤니티): 하루 2~4회 폴링 + 발견 즉시 검증 큐 투입. 게시물 작성일 기준
  3일 이내만 유효 신호로 처리하는 규정(최종 기획안 "탐색 범위 및 종료 조건")이 있어서,
  느리게 폴링하면 3일 창을 놓칠 수 있음. 3일 경과 시 discovery/verification 단계에서 자동 제외.

## 4. 재실행 트리거 원칙

- 정해진 달력이 아니라 "소스에 새 콘텐츠가 나타났을 때"가 재파싱의 기준.
- 원문 텍스트 해시 비교(diff)로, 실제로 바뀐 상품만 재파싱 — 전체 재파싱은 비용 낭비.

## 5. BE 연동 방식 — 모듈 통합으로 확정

- 서버를 하나만 운영하는 계획이라, AI 코드(Discovery/Extraction/Verification/Calculation/Summary)는
  별도 서비스로 분리하지 않고 BE의 FastAPI 앱 안에 파이썬 모듈/패키지 형태로 들어간다.
- 이 결정으로 DB도 BE와 완전히 공유(단일 DB) — "API로 호출하는 별도 서비스" 옵션에서
  가정했던 "AI가 자체 DB를 소유"는 더 이상 적용되지 않음. product/product_condition/special_offer
  테이블 설계는 BE와 함께 맞춰야 함.
- 후속 확인 필요 (BE 협의):
  - [ ] requirements.txt 의존성 병합 — 버전 충돌 여부(pydantic, fastapi 등) 확인
  - [ ] AI 코드가 BE 레포 내 어느 경로(예: app/ai/)로 들어가는지
  - [ ] product/product_condition/special_offer 테이블 스키마 — 오늘 검증한 Pydantic 필드
        (fin_co_no, fin_prdt_cd, kor_co_nm, fin_prdt_nm, join_way, intr_rate, intr_rate2 등) 기준으로 협의
  - [ ] 배치(주 1회)를 단일 서버 안에서 어떻게 돌릴지 — 앱 기동 시 APScheduler 등으로
        백그라운드 등록 vs 같은 서버에서 cron이 별도 스크립트(같은 AI 모듈 import) 실행

## 6. 확인 필요 / 오픈 이슈

- [ ] Claude API 콘솔에서 실제 quota(RPM/ITPM/OTPM, tier) 확인 — platform.claude.com/settings/limits
      (엘리스 ML API(GPT-4.1-mini) 발견으로 이 항목 자체가 아직 유효한지부터 재확인 필요)
- [ ] NFR-04 "LLM 호출 3개 지점" 표현과 위 "2곳" 결정의 불일치 — 팀/멘토링에서 정리 필요