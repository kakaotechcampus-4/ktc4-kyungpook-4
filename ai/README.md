# AI - 예적금 우대조건 Extraction 파이프라인

## 설정
1. `pip install -r requirements.txt`
2. `.env.example`을 `.env`로 복사하고 실제 키 채우기
   - `FSS_AUTH_KEY`: 금융감독원 공시 API 인증키
   - `OPENAI_API_KEY`, `OPENAI_BASE_URL`: 엘리스 ML API (Claude Sonnet 5)

## 구조
- `src/schemas/product.py`: FSS API 응답 스키마
- `src/schemas/extraction.py`: LLM 구조화(Extraction) 결과 스키마
- `scripts/test_extraction_verify.py`: Extraction + G3 검산(공시 우대폭 대조) 실행 스크립트
  - 불일치/실패 상품은 `logs/review_queue.json`에 격리됨