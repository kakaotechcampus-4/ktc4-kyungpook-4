"""상품 목록 응답 스키마 (캘린더 직접 기록에서 상품명 대신 고를 때)."""

from pydantic import BaseModel, Field


class ProductListItem(BaseModel):
    product_id: str | None = Field(description="신협·새마을금고는 조합마다 상품이 따로라 이름으로 묶어서 None")
    product_name: str
    product_type: str = Field(description="예금 | 적금 | 예탁금")
    on_sale: bool = Field(description="가장 최근 수집에도 있었던 상품. 아니면 예전에 수집됐다가 빠진 상품")
    periods: list[int] = Field(description="가입 가능 기간(개월)")
    base_rate: float | None = Field(description="기간 중 가장 높은 기본금리. 이름으로 묶은 경우 None")
    max_rate: float | None = Field(description="기간 중 가장 높은 최고금리. 이름으로 묶은 경우 None")


class ProductListOut(BaseModel):
    institution: str
    grouped_by_name: bool = Field(description="true 면 신협·새마을금고라 조합 상품을 이름으로 묶었다")
    items: list[ProductListItem]
