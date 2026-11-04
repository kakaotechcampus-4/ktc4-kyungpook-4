"""상품 목록 API."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.enums import PRODUCT_TYPES
from app.schemas.product import ProductListOut
from app.schemas.profile import BankLabel
from app.services import products as product_service

router = APIRouter(prefix="/products", tags=["products"])


@router.get(
    "",
    response_model=ProductListOut,
    summary="기관별 상품 목록 - 캘린더 직접 기록에서 상품명 대신 고를 때",
    description=(
        "지금 판매 중인 상품(on_sale=true)이 먼저, 예전에 수집됐다가 빠진 상품이 뒤에 온다. "
        "신협·새마을금고는 조합마다 상품이 따로라 이름으로 묶어 금리 없이 준다. "
        "공시 데이터에 없는 기관은 빈 목록 - FE 는 직접 입력으로 받는다."
    ),
)
async def list_products(
    session: Annotated[AsyncSession, Depends(get_session)],
    institution: Annotated[BankLabel, Query(description="FE 기관 선택지 이름 그대로 (예: 국민은행)")],
    product_type: Annotated[Literal[PRODUCT_TYPES] | None, Query(description="예금 | 적금 | 예탁금")] = None,
) -> ProductListOut:
    return await product_service.list_products(session, institution, product_type)
