"""Extraction(호출 A) 결과 스키마 - 우대조건 원문(spcl_cnd)을 구조화한 결과."""
from typing import List, Optional
from pydantic import BaseModel


class PreferentialCondition(BaseModel):
    """개별 우대조건 하나."""
    description: str  # 조건 설명 (예: "급여이체 실적 보유")
    bonus_rate: float  # 이 조건으로 얻는 우대금리 (%p 단위, 예: 0.2)
    applicable_term_months: Optional[int] = None  # 특정 만기(개월)에만 적용되면 그 값, 전체 만기 공통이면 None


class ExtractionResult(BaseModel):
    """spcl_cnd 원문 하나를 파싱한 결과."""
    conditions: List[PreferentialCondition]