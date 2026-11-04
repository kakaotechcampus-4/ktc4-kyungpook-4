"""기관별 상품 목록.

캘린더 직접 기록에서 사용자가 상품명을 타이핑하지 않고 고를 수 있게 한다.
상품 데이터는 9월 중순부터만 있고 직접 기록은 대개 예전에 가입한 상품이라, 날짜로 거르지 않고
지금 판매 중인 상품과 예전에 수집됐던 상품을 함께 준다 (판매 중인 것이 먼저).
"""

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import BatchRun
from app.models.institution import Institution
from app.models.product import Product, ProductOption
from app.schemas.product import ProductListItem, ProductListOut
from app.services.onboarding import BANK_CODES

# 선택지 하나가 기관 하나로 정해지지 않는 경우. 조합이 1,800곳이라 상품을 이름으로 묶는다
COOP_LABELS = {"신협": "신협", "새마을금고": "새마을금고"}  # 선택지 -> institution_type


async def list_products(session: AsyncSession, institution: str, product_type: str | None) -> ProductListOut:
    grouped = institution in COOP_LABELS
    code = BANK_CODES.get(institution)
    if not grouped and code is None:  # 공시 데이터에 없는 기관 - FE 는 직접 입력으로
        return ProductListOut(institution=institution, grouped_by_name=False, items=[])

    # 임포터는 빠진 상품을 지우지도 is_active 를 끄지도 않고, 넣을 때마다 product.run_id 를 그 임포트로
    # 바꾼다. 그래서 가장 최근 임포트에 들어 있었으면 판매 중이다. (snapshot_date 는 상품 종류별 공시
    # 기준일이라 같은 기관 안에서도 날짜가 달라 판단 기준으로 쓸 수 없다)
    latest_run = (
        select(func.max(BatchRun.run_id))
        .where(BatchRun.batch_type == "COLLECT", BatchRun.status == "SUCCESS")
        .scalar_subquery()
    )
    on_sale = func.bool_or(and_(Product.is_active, Product.run_id == latest_run))
    periods = func.array_agg(ProductOption.period_months.distinct())

    stmt: Select
    if grouped:
        stmt = (
            select(Product.product_name, Product.product_type, on_sale, periods)
            .join(Institution, Institution.institution_code == Product.institution_code)
            .where(Institution.institution_type == COOP_LABELS[institution])
            .group_by(Product.product_name, Product.product_type)
        )
    else:
        stmt = (
            select(
                Product.product_id,
                Product.product_name,
                Product.product_type,
                on_sale,
                periods,
                func.max(ProductOption.base_rate),
                func.max(ProductOption.max_rate),
            )
            .where(Product.institution_code == code)
            .group_by(Product.product_id, Product.product_name, Product.product_type)
        )
    stmt = stmt.outerjoin(ProductOption, ProductOption.product_id == Product.product_id)
    if product_type:
        stmt = stmt.where(Product.product_type == product_type)

    items = []
    for row in (await session.execute(stmt)).all():
        if grouped:
            name, kind, sale, months = row
            product_id, base, top = None, None, None
        else:
            product_id, name, kind, sale, months, base, top = row
        items.append(
            ProductListItem(
                product_id=product_id,
                product_name=name,
                product_type=kind,
                on_sale=bool(sale),
                periods=sorted(m for m in months if m is not None),
                base_rate=float(base) if base is not None else None,
                max_rate=float(top) if top is not None else None,
            )
        )
    items.sort(key=lambda i: (not i.on_sale, i.product_type, i.product_name))
    return ProductListOut(institution=institution, grouped_by_name=grouped, items=items)
