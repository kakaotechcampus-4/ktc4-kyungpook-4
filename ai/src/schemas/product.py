"""finlife API 원본 응답 스키마 - 정기예금 + 적금."""
from typing import Optional
from pydantic import BaseModel


class ProductBase(BaseModel):
    """정기예금/적금 공통 기본정보 (baseList)."""
    fin_co_no: str
    fin_prdt_cd: str
    kor_co_nm: str
    fin_prdt_nm: str
    join_way: Optional[str] = None
    join_member: str
    join_deny: str
    spcl_cnd: str
    max_limit: Optional[int] = None
    dcls_strt_day: str
    dcls_end_day: Optional[str] = None


class ProductOption(BaseModel):
    """정기예금 옵션 (optionList)."""
    fin_co_no: str
    fin_prdt_cd: str
    save_trm: str
    intr_rate_type: str
    intr_rate: float
    intr_rate2: float

    @property
    def max_bonus(self) -> float:
        """G3 검산 기준값 - 공시된 총 우대폭."""
        return round(self.intr_rate2 - self.intr_rate, 4)


class SavingOption(BaseModel):
    """적금 옵션 (optionList) - 정기예금과 달리 rsrv_type(적립방식) 있음."""
    fin_co_no: str
    fin_prdt_cd: str
    save_trm: str
    intr_rate_type: str
    rsrv_type: str  # S=정액적립식, F=자유적립식
    intr_rate: float
    intr_rate2: Optional[float] = None

    @property
    def max_bonus(self) -> Optional[float]:
        if self.intr_rate2 is None:
            return None
        return round(self.intr_rate2 - self.intr_rate, 4)