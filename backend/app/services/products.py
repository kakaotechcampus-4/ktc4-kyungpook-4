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
from app.schemas.product import BranchItem, BranchListOut, ProductListItem, ProductListOut
from app.services.onboarding import BANK_CODES

# 선택지 하나가 기관 하나로 정해지지 않는 경우. 조합이 2,000곳이라 지점(branch)을 고르지 않으면 상품을 이름으로 묶는다
COOP_LABELS = {"신협": "신협", "새마을금고": "새마을금고"}  # 선택지 -> institution_type


def branch_label(institution: str, name: str, region: str | None) -> str:
    # 신협은 이름이 지명뿐이고("순천") 지역이 비어 있다. 새마을금고는 이름에 '새마을금고'가 들어 있다
    label = name if institution in name else f"{name}{institution}"
    return f"{label} ({region})" if region else label


async def list_branches(session: AsyncSession, institution: str) -> BranchListOut:
    """신협·새마을금고 지점 전부 (상품이 있는 곳만). 지역 → 이름 순."""
    has_product = select(Product.product_id).where(Product.institution_code == Institution.institution_code).exists()
    rows = (
        await session.execute(
            select(Institution.institution_code, Institution.name, Institution.region)
            .where(Institution.institution_type == COOP_LABELS[institution], has_product)
            .order_by(Institution.region.nulls_last(), Institution.name)
        )
    ).all()
    items = [
        BranchItem(institution_code=code, name=name, region=region, label=branch_label(institution, name, region))
        for code, name, region in rows
    ]
    return BranchListOut(institution=institution, items=items)


async def list_products(
    session: AsyncSession, institution: str, product_type: str | None, branch: str | None = None
) -> ProductListOut:
    grouped = institution in COOP_LABELS
    code = BANK_CODES.get(institution)
    if grouped and branch is not None:  # 지점을 골랐으면 그 지점 상품을 은행처럼 금리와 함께 준다
        branch_type = await session.scalar(
            select(Institution.institution_type).where(Institution.institution_code == branch)
        )
        if branch_type != COOP_LABELS[institution]:  # 없는 지점이거나 다른 기관 종류
            return ProductListOut(institution=institution, grouped_by_name=False, items=[])
        grouped, code = False, branch
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
