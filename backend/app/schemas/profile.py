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


class ProfileOut(BaseModel):
    model_config = {"from_attributes": True}

    profile_id: int
    user_id: int
    capital: int
    monthly_saving: int
    period_months: int
    main_bank_code: str | None
    held_bank_codes: list[str]
    created_at: datetime
