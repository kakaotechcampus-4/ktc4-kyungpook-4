"""로드맵 숫자: 서비스를 쓴 기간과 지금까지 번 이자.

이자는 가입할 때 저장한 확정금리(user_holding.effective_rate)로 단리 계산하고 세후로 준다.
- 만기가 지난 상품: 만기까지의 이자 전부. 추천 화면과 같은 공식이라 그때 보여준 금액과 같다
- 만기 전 상품: 오늘까지 날짜만큼 쌓인 이자. 적금은 회차마다 낸 날부터 센다
- 그만둔 안(user_portfolio.closed_at): 그만둔 날까지

목표(goal_amount)는 진행중 안을 만기까지 유지했을 때 받는 돈 = 실제로 넣는 원금 + 만기 세후 이자.
가입 상품에서 매번 다시 계산한다 - 경로 위 현재 위치(active_total, 원금+이자)와 같은 기준이라
마지막 만기일에 정확히 목표에 닿고, 결과 화면에서 고른 안의 숫자와도 맞는다.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import kst_date
from app.models.portfolio import UserHolding, UserPortfolio
from app.models.product import Product, ProductOption
from app.models.profile import UserProfile
from app.models.user import AppUser

# 추천·가입과 같은 공식을 써야 만기 금액이 그때 보여준 숫자와 맞는다
from app.services.portfolio import _add_months, _deposit_interest, _installment_interest, _tax_context


@dataclass(frozen=True)
class Accrued:
    interest: Decimal  # 세전
    paid_principal: int  # 지금까지 넣은 원금
    total_principal: int  # 만기까지 넣을 원금 (조합 감면 한도 판정 기준)


@dataclass(frozen=True)
class RoadmapNumbers:
    started_at: date
    elapsed_months: int
    total_interest: int
    current_interest: int
    current_principal: int
    active_portfolio_id: int | None
    active_total: int  # 진행중 안의 넣은 원금 + 번 이자(세후). 만기된 상품도 포함해 줄지 않는다
    goal_amount: int | None
    goal_date: date | None


def _term_months(start: date, maturity: date) -> int:
    # 만기일은 가입일에 개월 수를 더해 만든다 (말일 보정 때문에 일(day)은 보지 않는다)
    return (maturity.year - start.year) * 12 + maturity.month - start.month


def elapsed_months(start: date, today: date) -> int:
    """다 채운 개월 수. 31일이 없는 달은 말일에 한 달을 채운다 (1/31 시작이면 2/27 은 0개월, 2/28 은 1개월).
    가입 만기일을 만드는 _add_months 와 같은 규칙이다."""
    months = (today.year - start.year) * 12 + today.month - start.month
    return max(0, months - (1 if today < _add_months(start, months) else 0))


def accrued(holding: UserHolding, until: date) -> Accrued:
    rate = Decimal(holding.effective_rate)
    start, maturity = holding.start_date, holding.maturity_date
    if maturity is None:
        return Accrued(Decimal(0), 0, 0)
    months = _term_months(start, maturity)
    end = min(until, maturity)

    if holding.monthly_amount is None:  # 예금·예탁금
        amount = holding.amount or 0
        if end < start:
            return Accrued(Decimal(0), 0, amount)
        if end >= maturity:
            return Accrued(_deposit_interest(amount, rate, months), amount, amount)
        return Accrued(Decimal(amount) * rate / 100 * (end - start).days / 365, amount, amount)

    monthly = holding.monthly_amount
    total = monthly * months
    if end >= maturity:
        return Accrued(_installment_interest(monthly, rate, months), total, total)
    interest, paid = Decimal(0), 0
    for k in range(months):  # k 회차(0부터)는 가입일에서 k 개월 뒤에 낸다
        paid_on = _add_months(start, k)
        if paid_on > end:
            break
        interest += Decimal(monthly) * rate / 100 * (end - paid_on).days / 365
        paid += monthly
    return Accrued(interest, paid, total)


async def build_roadmap(session: AsyncSession, user: AppUser, today: date) -> RoadmapNumbers:
    first_profile = await session.scalar(
        select(func.min(UserProfile.created_at)).where(UserProfile.user_id == user.user_id)
    )
    started_at = min(kst_date(d) for d in (user.created_at, first_profile) if d is not None)

    rows = (
        await session.execute(
            select(UserPortfolio, UserProfile, UserHolding, Product.institution_code)
            .join(UserProfile, UserProfile.profile_id == UserPortfolio.profile_id)
            .join(UserHolding, UserHolding.portfolio_id == UserPortfolio.portfolio_id)
            .outerjoin(ProductOption, ProductOption.option_id == UserHolding.option_id)
            .outerjoin(Product, Product.product_id == ProductOption.product_id)
            .where(UserPortfolio.user_id == user.user_id)
            # 가입 때와 같은 순서(예금 먼저, 그다음 적금)여야 조합 감면 한도가 같은 상품에 돌아간다
            .order_by(UserPortfolio.portfolio_id, UserHolding.holding_id)
        )
    ).all()

    total = current = current_principal = active_total = goal_amount = 0
    goal_date: date | None = None
    active = None
    taxes = {}  # 포트폴리오마다 조합 감면 한도를 따로 쓴다
    goal_tax = None  # 목표(만기 기준) 계산용. 감면 한도를 깎는 상태라 위의 것과 따로 둔다
    for portfolio, profile, holding, institution_code in rows:
        if portfolio.portfolio_id not in taxes:
            taxes[portfolio.portfolio_id] = _tax_context(profile, holding.start_date)
        until = kst_date(portfolio.closed_at) if portfolio.closed_at else today
        a = accrued(holding, min(until, today))
        # 상품이 지워져 기관 코드를 모르면 조합 감면 없이 일반과세로 본다 (이자를 부풀리지 않는 쪽)
        after_tax = taxes[portfolio.portfolio_id].after_tax(institution_code or "", a.interest, a.total_principal)
        total += after_tax.after_tax
        if portfolio.status == "진행중":
            active = portfolio
            active_total += a.paid_principal + after_tax.after_tax
            if holding.maturity_date is None or holding.maturity_date > today:
                current += after_tax.after_tax
                current_principal += a.paid_principal
            if holding.maturity_date is not None:
                if goal_tax is None:
                    goal_tax = _tax_context(profile, holding.start_date)
                full = accrued(holding, holding.maturity_date)
                tax = goal_tax.after_tax(institution_code or "", full.interest, full.total_principal)
                goal_amount += full.total_principal + tax.after_tax
                goal_date = max(goal_date or holding.maturity_date, holding.maturity_date)

    return RoadmapNumbers(
        started_at=started_at,
        elapsed_months=elapsed_months(started_at, today),
        total_interest=total,
        current_interest=current,
        current_principal=current_principal,
        active_portfolio_id=active.portfolio_id if active else None,
        active_total=active_total,
        goal_amount=(goal_amount or None) if active else None,
        goal_date=goal_date if active else None,
    )
