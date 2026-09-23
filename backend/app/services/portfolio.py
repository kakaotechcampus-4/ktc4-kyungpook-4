"""포트폴리오 계산 엔진.

우대조건(product_condition)은 아직 반영하지 않는다 - base_rate 만으로 계산한다.
product 테이블만 조회하므로 미검증 특판(product 에 행이 없는 상태)은 자동으로 제외된다.
"""

import calendar as calendar_module
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.institution import Institution
from app.models.portfolio import UserHolding, UserPortfolio
from app.models.product import Product, ProductOption
from app.models.profile import UserProfile
from app.schemas.calendar import CalendarEventOut
from app.schemas.portfolio import PortfolioOptionOut, PortfolioProductOut

TAX_RATE = Decimal("0.154")

# (표시 이름, 상품 몇 개까지 섞을지, 안내 문구)
TIER_SPECS: list[tuple[str, int, str]] = [
    ("단순형", 1, "가장 적은 계좌 수로 관리 부담을 줄인 조합"),
    ("균형형", 2, "안정성과 금리를 절충한 조합"),
    ("최대형", 3, "세후 수령액을 최대화한 조합"),
]


@dataclass
class Allocation:
    product: Product
    option: ProductOption
    institution_name: str
    amount: int  # 예금이면 원금, 적금이면 월 납입액


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar_module.monthrange(year, month)[1])
    return date(year, month, day)


def _deposit_after_tax(principal: int, rate: Decimal, months: int) -> int:
    interest = Decimal(principal) * rate / 100 * Decimal(months) / 12
    return int((interest * (1 - TAX_RATE)).to_integral_value())


def _installment_after_tax(monthly: int, rate: Decimal, months: int) -> int:
    # 정액적립식 단리: n회차 납입분은 만기까지 (전체기간 - n + 1)개월치 이자만 받는다
    interest = Decimal(monthly) * months * (months + 1) / 2 * rate / 100 / 12
    return int((interest * (1 - TAX_RATE)).to_integral_value())


async def _closest_period(session: AsyncSession, product_type: str, period_months: int) -> int | None:
    """상품 라인업이 1/3/6/12/24/36개월처럼 고정 구간이라, 요청 기간과 정확히 같은 옵션이
    없을 수 있다. 요청 기간 이하 중 가장 긴 것을, 그마저 없으면 가장 짧은 것을 쓴다."""
    stmt = (
        select(ProductOption.period_months)
        .join(Product, Product.product_id == ProductOption.product_id)
        .where(Product.product_type == product_type, Product.is_active.is_(True), Product.parse_status == "PARSED")
        .distinct()
    )
    available = sorted((await session.execute(stmt)).scalars().all())
    if not available:
        return None
    not_exceeding = [p for p in available if p <= period_months]
    return max(not_exceeding) if not_exceeding else min(available)


async def _matching_options(
    session: AsyncSession, product_type: str, period_months: int
) -> tuple[int | None, list[tuple[Product, ProductOption, str]]]:
    matched_period = await _closest_period(session, product_type, period_months)
    if matched_period is None:
        return None, []

    stmt = (
        select(Product, ProductOption, Institution.name)
        .join(ProductOption, ProductOption.product_id == Product.product_id)
        .join(Institution, Institution.institution_code == Product.institution_code)
        .where(
            Product.product_type == product_type,
            Product.is_active.is_(True),
            Product.parse_status == "PARSED",
            ProductOption.period_months == matched_period,
        )
        .order_by(ProductOption.base_rate.desc())
    )
    rows = (await session.execute(stmt)).all()
    return matched_period, [(p, o, name) for p, o, name in rows]


def _effective_cap(product: Product, cap_field: str, period_months: int) -> int | None:
    """월 납입 한도(monthly_cap)와 총 납입 한도(amount_cap)를 함께 반영한다.

    시드 데이터는 적금 상품에 amount_cap(총 납입 한도)만 채워둔 경우가 많아,
    monthly_cap 만 보면 사실상 무제한으로 배분되어 버린다."""
    direct_cap = getattr(product, cap_field)
    caps = [c for c in (direct_cap,) if c is not None]
    if cap_field == "monthly_cap" and product.amount_cap:
        caps.append(product.amount_cap // period_months)
    return min(caps) if caps else None


def _allocate_greedy(
    total: int,
    candidates: list[tuple[Product, ProductOption, str]],
    cap_field: str,
    max_products: int,
) -> list[Allocation]:
    """금리 높은 순으로, 상품별 한도(cap)까지 채우며 배분한다."""
    allocations: list[Allocation] = []
    remaining = total
    for product, option, institution_name in candidates[:max_products]:
        if remaining <= 0:
            break
        cap = _effective_cap(product, cap_field, option.period_months)
        amount = min(remaining, cap) if cap else remaining
        if amount <= 0:
            continue
        allocations.append(Allocation(product=product, option=option, institution_name=institution_name, amount=amount))
        remaining -= amount
    if remaining > 0 and allocations:
        # 후보 상품들의 한도를 다 채우고도 남으면, 한도 초과라도 마지막 상품에 몰아넣는다
        allocations[-1].amount += remaining
    return allocations


class TierAllocations:
    def __init__(
        self, reason: str, period_months: int, deposit_allocs: list[Allocation], installment_allocs: list[Allocation]
    ) -> None:
        self.reason = reason
        self.period_months = period_months  # 실제로 매칭된 기간. 프로필 요청 기간과 다를 수 있다
        self.deposit_allocs = deposit_allocs
        self.installment_allocs = installment_allocs


async def build_tiers(session: AsyncSession, profile: UserProfile) -> dict[str, TierAllocations]:
    deposit_period, deposits = await _matching_options(session, "예금", profile.period_months)
    installment_period, installments = await _matching_options(session, "적금", profile.period_months)

    tiers: dict[str, TierAllocations] = {}
    for tier_name, max_products, reason in TIER_SPECS:
        deposit_allocs = (
            _allocate_greedy(profile.capital, deposits, "amount_cap", max_products)
            if profile.capital > 0 and deposit_period is not None
            else []
        )
        installment_allocs = (
            _allocate_greedy(profile.monthly_saving, installments, "monthly_cap", max_products)
            if profile.monthly_saving > 0 and installment_period is not None
            else []
        )
        tiers[tier_name] = TierAllocations(
            reason, deposit_period or installment_period or profile.period_months, deposit_allocs, installment_allocs
        )
    return tiers


def _to_product_out(alloc: Allocation, after_tax: int) -> PortfolioProductOut:
    return PortfolioProductOut(
        institution_name=alloc.institution_name,
        product_name=alloc.product.product_name,
        term_months=alloc.option.period_months,
        interest_rate=float(alloc.option.base_rate),
        allocated_amount=alloc.amount,
        after_tax_interest=after_tax,
    )


def to_option_out(tier_name: str, allocations: TierAllocations) -> PortfolioOptionOut:
    products: list[PortfolioProductOut] = []
    after_tax_total = 0

    for alloc in allocations.deposit_allocs:
        after_tax = _deposit_after_tax(alloc.amount, alloc.option.base_rate, alloc.option.period_months)
        after_tax_total += after_tax
        products.append(_to_product_out(alloc, after_tax))

    for alloc in allocations.installment_allocs:
        after_tax = _installment_after_tax(alloc.amount, alloc.option.base_rate, alloc.option.period_months)
        after_tax_total += after_tax
        products.append(_to_product_out(alloc, after_tax))

    return PortfolioOptionOut(
        tier=tier_name, products=products, after_tax_total=after_tax_total, reason=allocations.reason
    )


async def persist_portfolio(
    session: AsyncSession, profile: UserProfile, tier_name: str, allocations: TierAllocations
) -> UserPortfolio:
    today = date.today()
    maturity_date = _add_months(today, allocations.period_months)

    portfolio = UserPortfolio(
        user_id=profile.user_id,
        profile_id=profile.profile_id,
        portfolio_type=tier_name,
        goal_amount=(profile.capital + profile.monthly_saving * profile.period_months) or None,
        goal_date=maturity_date,
        status="진행중",
    )
    session.add(portfolio)
    await session.flush()  # portfolio_id 발급

    after_tax_total = 0
    for alloc in allocations.deposit_allocs:
        after_tax_total += _deposit_after_tax(alloc.amount, alloc.option.base_rate, alloc.option.period_months)
        session.add(
            UserHolding(
                portfolio_id=portfolio.portfolio_id,
                option_id=alloc.option.option_id,
                institution=alloc.institution_name,
                product_name=alloc.product.product_name,
                amount=alloc.amount,
                base_rate=alloc.option.base_rate,
                effective_rate=alloc.option.base_rate,
                max_rate=alloc.option.max_rate,
                start_date=today,
                maturity_date=_add_months(today, alloc.option.period_months),
            )
        )
    for alloc in allocations.installment_allocs:
        after_tax_total += _installment_after_tax(alloc.amount, alloc.option.base_rate, alloc.option.period_months)
        session.add(
            UserHolding(
                portfolio_id=portfolio.portfolio_id,
                option_id=alloc.option.option_id,
                institution=alloc.institution_name,
                product_name=alloc.product.product_name,
                monthly_amount=alloc.amount,
                base_rate=alloc.option.base_rate,
                effective_rate=alloc.option.base_rate,
                max_rate=alloc.option.max_rate,
                start_date=today,
                maturity_date=_add_months(today, alloc.option.period_months),
            )
        )

    portfolio.after_tax_total = after_tax_total
    await session.commit()
    await session.refresh(portfolio)
    return portfolio


async def get_calendar_events(session: AsyncSession, portfolio_id: int) -> list[CalendarEventOut]:
    stmt = select(UserHolding).where(UserHolding.portfolio_id == portfolio_id, UserHolding.status == "유지중")
    holdings = (await session.execute(stmt)).scalars().all()

    today = date.today()
    events: list[CalendarEventOut] = []
    for holding in holdings:
        if holding.monthly_amount is not None:
            round_number = 1
            payment_date = _add_months(holding.start_date, round_number)
            while holding.maturity_date is None or payment_date <= holding.maturity_date:
                if payment_date >= today:
                    events.append(
                        CalendarEventOut(
                            date=payment_date,
                            institution_name=holding.institution,
                            product_name=holding.product_name,
                            installment_round=round_number,
                        )
                    )
                round_number += 1
                payment_date = _add_months(holding.start_date, round_number)
                if holding.maturity_date and payment_date > holding.maturity_date:
                    break
        elif holding.maturity_date and holding.maturity_date >= today:
            events.append(
                CalendarEventOut(
                    date=holding.maturity_date,
                    institution_name=holding.institution,
                    product_name=holding.product_name,
                    installment_round=0,
                )
            )

    events.sort(key=lambda e: e.date)
    return events
