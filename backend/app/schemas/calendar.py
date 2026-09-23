"""캘린더 이벤트 응답 스키마."""

from datetime import date

from pydantic import BaseModel


class CalendarEventOut(BaseModel):
    date: date
    institution_name: str
    product_name: str
    installment_round: int  # 적금 납입 회차. 예금 만기 이벤트는 0
