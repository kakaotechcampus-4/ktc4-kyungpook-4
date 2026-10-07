"""Summary(호출 B) 결과 스키마 - 포트폴리오 3개 티어 각각의 추천 설명(reason).

BE `backend/app/schemas/portfolio.py`의 PortfolioOptionOut.reason 필드에 그대로
들어갈 값을 만드는 게 이 스키마의 목적. AI는 reason(설명 문장)만 만들고, tier/
products/after_tax_total 등 숫자·구조는 전부 계산 엔진이 이미 만들어둔 값을
그대로 쓴다(AI가 숫자를 새로 만들거나 바꾸지 않음)."""
from typing import List
from pydantic import BaseModel


class TierReason(BaseModel):
    tier: str  # "단순형" | "균형형" | "최대형" - BE PortfolioOptionOut.tier와 동일한 문자열
    reason: str  # 사람이 읽는 추천 설명 (3문단, 문단 사이 \n\n, 4~6문장)


class SummaryResult(BaseModel):
    reasons: List[TierReason]
