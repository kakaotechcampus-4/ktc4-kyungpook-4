"""캘린더 이벤트 응답 스키마."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class CalendarEventOut(BaseModel):
    date: date
    institution_name: str
    product_name: str
    installment_round: int = Field(description="적금 납입 회차(가입일이 1회차). 만기 이벤트는 0")
    event_type: Literal["납입", "만기"]
    amount: int = Field(description="납입이면 그 회차 납입액, 만기면 만기까지 넣은 원금 합계(원, 이자 제외)")
