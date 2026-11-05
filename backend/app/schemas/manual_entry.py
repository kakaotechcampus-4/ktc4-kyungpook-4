"""캘린더 직접 기록 요청/응답 스키마."""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class ManualEntryCreate(BaseModel):
    entry_date: date
    institution_name: str = Field(min_length=1, max_length=100, description="FE 기관 선택지 이름 그대로")
    product_id: str | None = Field(default=None, description="GET /products 목록에서 골랐으면 그 product_id")
    product_name: str = Field(min_length=1, max_length=200, description="목록에서 골랐어도 이름을 같이 보낸다")
    amount: int = Field(gt=0, description="금액(원)")
    memo: str | None = Field(default=None, max_length=1000)

    @field_validator("institution_name", "product_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("비어 있을 수 없습니다")
        return v

    @field_validator("memo")
    @classmethod
    def _empty_memo_is_none(cls, v: str | None) -> str | None:
        # FE 는 메모를 안 쓰면 "" 를 보낸다
        return v.strip() or None if v is not None else None


class ManualEntryOut(BaseModel):
    model_config = {"from_attributes": True}

    entry_id: int
    entry_date: date
    institution_name: str
    product_id: str | None
    product_name: str
    amount: int
    memo: str | None
    created_at: datetime
