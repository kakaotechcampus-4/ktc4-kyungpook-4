"""상품 목록 응답 스키마 (캘린더 직접 기록에서 상품명 대신 고를 때)."""

from pydantic import BaseModel, Field


class ProductListItem(BaseModel):
    product_id: str | None = Field(description="신협·새마을금고를 지점 없이 조회하면 이름으로 묶어서 None")
    product_name: str
    product_type: str = Field(description="예금 | 적금 | 예탁금")
    on_sale: bool = Field(description="가장 최근 수집에도 있었던 상품. 아니면 예전에 수집됐다가 빠진 상품")
    periods: list[int] = Field(description="가입 가능 기간(개월)")
    base_rate: float | None = Field(description="기간 중 가장 높은 기본금리. 이름으로 묶은 경우 None")
    max_rate: float | None = Field(description="기간 중 가장 높은 최고금리. 이름으로 묶은 경우 None")


class ProductListOut(BaseModel):
    institution: str
    grouped_by_name: bool = Field(description="true 면 신협·새마을금고를 지점 없이 조회해 상품을 이름으로 묶었다")
    items: list[ProductListItem]


class BranchItem(BaseModel):
    institution_code: str = Field(description="GET /products 의 branch 로 넘긴다")
    name: str = Field(description="공시 기관명 (예: 가창새마을금고 본점, 순천)")
    region: str | None = Field(description="영업 지역 (예: 대구 달성군). 신협은 데이터에 없어 null")
    label: str = Field(
        description="화면 표시용 (예: 가창새마을금고 본점 (대구 달성군), 순천신협). 직접 기록의 기관명으로도 쓴다"
    )


class BranchListOut(BaseModel):
    institution: str
    items: list[BranchItem]
