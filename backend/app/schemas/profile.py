"""프로필 요청/응답 스키마."""

from datetime import datetime

from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    user_id: int | None = Field(default=None, description="없으면 익명 사용자를 새로 만든다")
    lump_sum: int = Field(default=0, ge=0)
    monthly_saving: int = Field(default=0, ge=0)
    period_months: int = Field(gt=0)


class ProfileOut(BaseModel):
    model_config = {"from_attributes": True}

    profile_id: int
    user_id: int
    capital: int
    monthly_saving: int
    period_months: int
    created_at: datetime
