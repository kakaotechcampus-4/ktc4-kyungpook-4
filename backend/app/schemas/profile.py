"""프로필 요청/응답 스키마."""

from datetime import datetime

from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    user_id: int | None = Field(default=None, description="없으면 익명 사용자를 새로 만든다")
    lump_sum: int = Field(default=0, ge=0)
    monthly_saving: int = Field(default=0, ge=0)
    period_months: int = Field(gt=0)
    # 은행은 이름이 아니라 institution_code 로 받는다. FE 선택지("국민은행")와 DB 정식명칭
    # ("국민은행", "주식회사 카카오뱅크" 등)이 서로 달라 이름으로는 비교할 수 없다.
    main_bank_code: str | None = Field(default=None, description="주거래은행 institution_code")
    held_bank_codes: list[str] = Field(default_factory=list, description="보유(거래 중) 은행 institution_code 목록")
    # 신협·새마을금고 조합 예탁금 세금 감면 판정용 (STEP3). 모르면 null - 혜택을 부풀리지 않는 쪽으로 계산한다.
    accepts_membership: bool | None = Field(default=None, description="조합원이거나 조합원 가입(출자) 의향이 있음")
    coop_tax_eligible: bool | None = Field(default=None, description="총급여 7천만원 이하")
    coop_exempt_used: int | None = Field(default=None, ge=0, description="다른 조합에 이미 감면으로 넣어 둔 예탁금(원)")


class ProfileOut(BaseModel):
    model_config = {"from_attributes": True}

    profile_id: int
    user_id: int
    capital: int
    monthly_saving: int
    period_months: int
    main_bank_code: str | None
    held_bank_codes: list[str]
    accepts_membership: bool | None
    coop_tax_eligible: bool | None
    coop_exempt_used: int | None
    created_at: datetime
