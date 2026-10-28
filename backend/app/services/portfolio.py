"""포트폴리오 계산 엔진.

[티어 - 2026-10-13 기획 확정]
  단순형 : 이미 충족한 우대조건만으로 받을 수 있는 최대 실수령액. 주거래·보유 은행만, 새 가입 없음.
  균형형 : 약간의 행동 변화(새 기관 1곳 가입, 마케팅동의·비대면가입·자동이체)로 받는 최대 실수령액.
  최대형 : 모든 우대조건 달성을 가정한 최대 실수령액.
  안정형 : 1금융(은행)만으로 구성. 우대조건 범위는 균형형과 같다.
  단일형 : 주거래은행 상품 중 실효금리 1위 하나에 전액. 추천안이 아니라 비교 기준선(baseline)이다.
어떤 우대조건을 인정하는지는 services/conditions.py, 세금은 services/tax.py 가 정한다.

후보는 세후 기준 금리(실효금리 x (1 - 기대 세율)) 높은 순으로 고른다. 단일형을 뺀 안은
한 기관에 원금 1억원(예금자보호 한도)을 넘게 넣지 않는다.
product 테이블만 조회하므로 미검증 특판(product 에 행이 없는 상태)은 자동으로 제외된다.

티어마다 추천 이유(reason)는 AI 파트의 Summary(ktc4_ai.summary)가 만든다. 숫자는 여기서
계산한 값을 그대로 넘기고, AI 는 문장으로 옮기기만 한다.
"""

import asyncio
import calendar as calendar_module
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

# ai/ 패키지는 기존/신규 은행 판정·단순형 대비 차액 같은 파생값 계산(_enrich_options)도 함께 제공한다.
# 같은 값을 BE 에서 따로 계산하면 reason 문장 속 숫자와 응답 필드가 어긋날 수 있어 그대로 가져다 쓴다.
from ktc4_ai import config as ai_config
from ktc4_ai.summary import _enrich_options, generate_summary
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.institution import Institution
from app.models.portfolio import UserHolding, UserHoldingCondition, UserPortfolio
from app.models.product import Product, ProductCondition, ProductOption
from app.models.profile import UserProfile, UserProfileBank
from app.schemas.calendar import CalendarEventOut
from app.schemas.portfolio import BaselineOut, PortfolioOptionOut, PortfolioProductOut
from app.services.conditions import AppliedCondition, Scope, evaluate
from app.services.tax import TaxContext, is_coop

SIMPLE_TIER = "단순형"
BALANCED_TIER = "균형형"
MAX_TIER = "최대형"
STABLE_TIER = "안정형"

DEPOSIT_PROTECTION_LIMIT = 100_000_000  # 예금자보호 한도. 기관별 원금 합계를 여기까지만 담는다
COMPREHENSIVE_TAX_THRESHOLD = 20_000_000  # 금융소득종합과세 기준 (연간 이자·배당)
FIRST_TIER_INSTITUTION_TYPE = "은행"  # 1금융권


@dataclass(frozen=True)
class TierSpec:
    name: str
    scope: Scope  # 인정하는 우대조건 범위
    max_new_institutions: int | None  # 새로 가입하는 기관 수 상한. None = 제한 없음
    bank_only: bool = False  # 1금융만


TIER_SPECS = (
    TierSpec(SIMPLE_TIER, Scope.SIMPLE, max_new_institutions=0),
    TierSpec(BALANCED_TIER, Scope.BALANCED, max_new_institutions=1),
    TierSpec(MAX_TIER, Scope.MAX, max_new_institutions=None),
    TierSpec(STABLE_TIER, Scope.BALANCED, max_new_institutions=None, bank_only=True),
)


@dataclass
class Candidate:
    product: Product
    option: ProductOption
    institution_name: str
    institution_type: str
    conditions: list[ProductCondition]


@dataclass
class Allocation:
    product: Product
    option: ProductOption
    institution_name: str
    amount: int  # 예금이면 원금, 적금이면 월 납입액
    effective_rate: Decimal  # 기본금리 + 인정된 우대폭 (최고금리 상한)
    applied: list[AppliedCondition] = field(default_factory=list)


class TierAllocations:
    def __init__(
        self, period_months: int, deposit_allocs: list[Allocation], installment_allocs: list[Allocation]
    ) -> None:
        self.period_months = period_months  # 실제로 매칭된 기간. 프로필 요청 기간과 다를 수 있다
        self.deposit_allocs = deposit_allocs
        self.installment_allocs = installment_allocs


@dataclass
class PortfolioPlan:
    tiers: dict[str, TierAllocations]
    baseline: TierAllocations | None  # 단일형. 주거래은행을 모르거나 그 은행 상품이 없으면 None


@dataclass
class _BankInfo:
    """사용자의 거래 은행. 신규 가입 여부 판정에 쓴다."""

    main_bank_code: str | None
    codes: set[str]  # 주거래 + 보유. 비어 있으면 '모름'

    def is_main(self, code: str) -> bool:
        return code == self.main_bank_code

    def is_new(self, code: str) -> bool:
        """확실히 새로 가입해야 하는 기관인지. 신협·새마을금고는 조합마다 따로 가입하므로 항상 신규.
        은행 입력이 없으면 판정할 수 없어 False(신규 아님)로 둔다 - 신규고객 우대를 부풀리지 않고,
        단순형·균형형의 기관 제한도 입력 없는 사용자에게 걸지 않기 위해서다."""
        return is_coop(code) or (bool(self.codes) and code not in self.codes)


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar_module.monthrange(year, month)[1])
    return date(year, month, day)


def _deposit_interest(principal: int, rate: Decimal, months: int) -> Decimal:
    return Decimal(principal) * rate / 100 * Decimal(months) / 12


def _installment_interest(monthly: int, rate: Decimal, months: int) -> Decimal:
    # 정액적립식 단리: n회차 납입분은 만기까지 (전체기간 - n + 1)개월치 이자만 받는다
    return Decimal(monthly) * months * (months + 1) / 2 * rate / 100 / 12


def _tax_context(profile: UserProfile, join_date: date) -> TaxContext:
    return TaxContext.for_profile(
        join_year=join_date.year,
        accepts_membership=profile.accepts_membership,
        coop_tax_eligible=profile.coop_tax_eligible,
        coop_exempt_used=profile.coop_exempt_used,
    )


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
) -> tuple[int | None, list[Candidate]]:
    matched_period = await _closest_period(session, product_type, period_months)
    if matched_period is None:
        return None, []

    stmt = (
        select(Product, ProductOption, Institution.name, Institution.institution_type)
        .join(ProductOption, ProductOption.product_id == Product.product_id)
        .join(Institution, Institution.institution_code == Product.institution_code)
        .where(
            Product.product_type == product_type,
            Product.is_active.is_(True),
            Product.parse_status == "PARSED",
            ProductOption.period_months == matched_period,
        )
    )
    rows = (await session.execute(stmt)).all()

    conditions: dict[str, list[ProductCondition]] = defaultdict(list)
    if rows:
        product_ids = {p.product_id for p, *_ in rows}
        cond_stmt = select(ProductCondition).where(ProductCondition.product_id.in_(product_ids))
        for cond in (await session.execute(cond_stmt)).scalars():
            conditions[cond.product_id].append(cond)

    return matched_period, [Candidate(p, o, name, itype, conditions[p.product_id]) for p, o, name, itype in rows]


def _effective_cap(product: Product, cap_field: str, period_months: int) -> int | None:
    """월 납입 한도(monthly_cap)와 총 납입 한도(amount_cap)를 함께 반영한다.

    시드 데이터는 적금 상품에 amount_cap(총 납입 한도)만 채워둔 경우가 많아,
    monthly_cap 만 보면 사실상 무제한으로 배분되어 버린다."""
    direct_cap = getattr(product, cap_field)
    caps = [c for c in (direct_cap,) if c is not None]
    if cap_field == "monthly_cap" and product.amount_cap:
        caps.append(product.amount_cap // period_months)
    return min(caps) if caps else None


@dataclass
class _Ranked:
    candidate: Candidate
    effective_rate: Decimal
    applied: list[AppliedCondition]


def _rank(
    candidates: list[Candidate],
    spec: TierSpec,
    profile: UserProfile,
    banks: _BankInfo,
    tax: TaxContext,
) -> list[_Ranked]:
    """이 티어에서 쓸 수 있는 후보를 세후 기준 금리 높은 순으로 정렬한다."""
    ranked = []
    for c in candidates:
        code = c.product.institution_code
        if spec.bank_only and c.institution_type != FIRST_TIER_INSTITUTION_TYPE:
            continue
        if spec.max_new_institutions == 0 and banks.is_new(code):
            continue
        if profile.accepts_membership is False and is_coop(code):
            continue  # 조합원 가입을 거부하면 예탁금에 가입할 수 없다 (모름이면 남겨 두고 일반과세로 계산)
        rate, applied = evaluate(
            c.option,
            c.conditions,
            spec.scope,
            profile,
            is_main_bank=banks.is_main(code),
            is_new_institution=banks.is_new(code),
        )
        ranked.append(_Ranked(c, rate, applied))
    ranked.sort(
        key=lambda r: r.effective_rate * (1 - tax.effective_rate(r.candidate.product.institution_code)), reverse=True
    )
    return ranked


@dataclass
class _TierState:
    """한 티어 안에서 예금·적금 배분이 함께 지키는 제약."""

    used_products: set[str] = field(default_factory=set)
    new_institutions: set[str] = field(default_factory=set)
    principal_by_institution: dict[str, int] = field(default_factory=lambda: defaultdict(int))


def _allocate_greedy(
    total: int,
    ranked: list[_Ranked],
    cap_field: str,
    spec: TierSpec,
    banks: _BankInfo,
    state: _TierState,
) -> list[Allocation]:
    """세후 금리 높은 순으로, 상품 한도와 기관별 예금자보호 한도까지 채우며 배분한다.

    1위 상품이 한도 안에서 다 받으면 상품 하나로 끝난다. 한도에 걸릴 때만 다음 상품을 쓴다.
    후보를 다 써도 남으면 마지막 상품에 몰아넣는다 (한도 초과지만 돈을 버리지 않기 위해).
    """
    allocations: list[Allocation] = []
    remaining = total
    for r in ranked:
        if remaining <= 0:
            break
        product, option = r.candidate.product, r.candidate.option
        code = product.institution_code
        if product.product_id in state.used_products:
            continue  # 같은 상품의 채널만 다른 옵션
        if (
            banks.is_new(code)
            and code not in state.new_institutions
            and spec.max_new_institutions is not None
            and len(state.new_institutions) >= spec.max_new_institutions
        ):
            continue

        months = option.period_months if cap_field == "monthly_cap" else 1
        protection_room = (DEPOSIT_PROTECTION_LIMIT - state.principal_by_institution[code]) // months
        cap = _effective_cap(product, cap_field, option.period_months)
        amount = min(remaining, protection_room, cap if cap else remaining)
        if amount <= 0:
            continue
        allocations.append(
            Allocation(product, option, r.candidate.institution_name, amount, r.effective_rate, r.applied)
        )
        remaining -= amount
        state.used_products.add(product.product_id)
        state.principal_by_institution[code] += amount * months
        if banks.is_new(code):
            state.new_institutions.add(code)
    if remaining > 0 and allocations:
        # 후보 상품들의 한도를 다 채우고도 남으면, 한도 초과라도 마지막 상품에 몰아넣는다
        allocations[-1].amount += remaining
    return allocations


def _best_single(
    total: int, candidates: list[Candidate], profile: UserProfile, banks: _BankInfo, tax: TaxContext
) -> list[Allocation]:
    """단일형: 주거래은행 상품 중 세후 기준 1위 하나에 전액. 한도·예금자보호는 보지 않는다."""
    spec = TierSpec("단일형", Scope.SIMPLE, max_new_institutions=None)
    main_only = [c for c in candidates if banks.is_main(c.product.institution_code)]
    ranked = _rank(main_only, spec, profile, banks, tax)
    if total <= 0 or not ranked:
        return []
    top = ranked[0]
    return [
        Allocation(
            top.candidate.product,
            top.candidate.option,
            top.candidate.institution_name,
            total,
            top.effective_rate,
            top.applied,
        )
    ]


async def get_held_bank_codes(session: AsyncSession, profile: UserProfile) -> list[str]:
    # relationship lazy load 는 async 세션에서 쓸 수 없어 직접 조회한다
    stmt = select(UserProfileBank.institution_code).where(UserProfileBank.profile_id == profile.profile_id)
    return list((await session.execute(stmt)).scalars().all())


async def build_tiers(session: AsyncSession, profile: UserProfile) -> PortfolioPlan:
    deposit_period, deposits = await _matching_options(session, "예금", profile.period_months)
    installment_period, installments = await _matching_options(session, "적금", profile.period_months)
    period = deposit_period or installment_period or profile.period_months

    held = set(await get_held_bank_codes(session, profile))
    banks = _BankInfo(profile.main_bank_code, held | ({profile.main_bank_code} if profile.main_bank_code else set()))
    # 정렬에 쓰는 기대 세율만 본다. 실제 한도 차감은 세금 계산 단계에서 티어마다 새로 한다
    tax = _tax_context(profile, date.today())
    use_deposit = profile.capital > 0 and deposit_period is not None
    use_installment = profile.monthly_saving > 0 and installment_period is not None

    tiers: dict[str, TierAllocations] = {}
    for spec in TIER_SPECS:
        state = _TierState()
        deposit_allocs = (
            _allocate_greedy(
                profile.capital, _rank(deposits, spec, profile, banks, tax), "amount_cap", spec, banks, state
            )
            if use_deposit
            else []
        )
        installment_allocs = (
            _allocate_greedy(
                profile.monthly_saving,
                _rank(installments, spec, profile, banks, tax),
                "monthly_cap",
                spec,
                banks,
                state,
            )
            if use_installment
            else []
        )
        tiers[spec.name] = TierAllocations(period, deposit_allocs, installment_allocs)

    baseline = None
    if profile.main_bank_code:
        base_deposits = _best_single(profile.capital, deposits, profile, banks, tax) if use_deposit else []
        base_installments = (
            _best_single(profile.monthly_saving, installments, profile, banks, tax) if use_installment else []
        )
        if base_deposits or base_installments:
            baseline = TierAllocations(period, base_deposits, base_installments)
    return PortfolioPlan(tiers, baseline)


@dataclass
class _TierNumbers:
    products: list[PortfolioProductOut]
    after_tax_total: int
    tax_saving: int
    over_comprehensive_tax: bool


def _calc(allocations: TierAllocations, tax: TaxContext) -> _TierNumbers:
    """배분마다 세후 이자를 구한다. 추천 응답과 가입 저장이 같은 값을 쓰도록 여기 한 곳에서만 계산한다.

    조합 예탁금 감면 한도는 포트폴리오 전체가 나눠 쓰므로 tax 의 남은 한도가 순서대로 줄어든다.
    """
    results = {"deposit": [], "installment": []}
    for kind, allocs in (("deposit", allocations.deposit_allocs), ("installment", allocations.installment_allocs)):
        for alloc in allocs:
            months = alloc.option.period_months
            if kind == "deposit":
                interest, principal = _deposit_interest(alloc.amount, alloc.effective_rate, months), alloc.amount
            else:
                interest = _installment_interest(alloc.amount, alloc.effective_rate, months)
                principal = alloc.amount * months
            results[kind].append((alloc, tax.after_tax(alloc.product.institution_code, interest, principal)))

    pairs = results["deposit"] + results["installment"]
    products = [
        PortfolioProductOut(
            institution_code=alloc.product.institution_code,
            institution_name=alloc.institution_name,
            product_name=alloc.product.product_name,
            term_months=alloc.option.period_months,
            base_rate=float(alloc.option.base_rate),
            interest_rate=float(alloc.effective_rate),
            allocated_amount=alloc.amount,
            after_tax_interest=result.after_tax,
            applied_conditions=[a.to_out() for a in alloc.applied],
        )
        for alloc, result in pairs
    ]
    # 만기에 이자를 한 번에 받으므로 만기 해의 금융소득으로 본다. 분리과세된 감면분은 합산하지 않는다
    general_interest = sum((r.general_interest for _, r in pairs), Decimal("0"))
    return _TierNumbers(
        products=products,
        after_tax_total=sum(r.after_tax for _, r in pairs),
        tax_saving=sum(r.tax_saving for _, r in pairs),
        over_comprehensive_tax=general_interest > COMPREHENSIVE_TAX_THRESHOLD,
    )


def _baseline_out(baseline: TierAllocations, profile: UserProfile, today: date) -> BaselineOut:
    numbers = _calc(baseline, _tax_context(profile, today))
    principal = sum(a.amount for a in baseline.deposit_allocs) + sum(
        a.amount * a.option.period_months for a in baseline.installment_allocs
    )
    return BaselineOut(
        institution_name=numbers.products[0].institution_name,
        product_name=" + ".join(p.product_name for p in numbers.products),
        products=numbers.products,
        after_tax_total=numbers.after_tax_total,
        exceeds_protection=principal > DEPOSIT_PROTECTION_LIMIT,
    )


async def recommend_options(
    session: AsyncSession, profile: UserProfile, plan: PortfolioPlan
) -> tuple[list[PortfolioOptionOut], BaselineOut | None]:
    """티어들을 응답 형태로 만들고 AI Summary 로 reason 을 채운다."""
    today = date.today()
    raw_options = []
    for tier_name, allocations in plan.tiers.items():
        # 티어는 서로 다른 안이라 감면 한도도 티어마다 새로 시작한다
        numbers = _calc(allocations, _tax_context(profile, today))
        raw_options.append(
            {
                "tier": tier_name,
                "products": [p.model_dump() for p in numbers.products],
                "after_tax_total": numbers.after_tax_total,
                "tax_saving_won": numbers.tax_saving,
                "over_comprehensive_tax": numbers.over_comprehensive_tax,
            }
        )
    baseline = _baseline_out(plan.baseline, profile, today) if plan.baseline else None
    baseline_ctx = (
        {
            "institution_name": baseline.institution_name,
            "product_name": baseline.product_name,
            "after_tax_total": baseline.after_tax_total,
            "exceeds_protection": baseline.exceeds_protection,
        }
        if baseline
        else None
    )

    held_bank_codes = await get_held_bank_codes(session, profile)
    # 은행 입력이 전혀 없으면 None 으로 넘긴다 -> 기존/신규 은행 여부를 "판정 불가"로 두고 언급하지 않는다
    user_context = (
        {"main_bank_code": profile.main_bank_code, "held_bank_codes": held_bank_codes}
        if profile.main_bank_code or held_bank_codes
        else None
    )

    # generate_summary 는 동기 함수이고 실패 시 sleep 하며 재시도한다. 이벤트 루프를 막지 않게 스레드로 돌린다.
    # 키가 없으면 어차피 실패하므로 재시도 대기 없이 바로 기본 문구로 넘어가게 한다.
    retries = 3 if ai_config.OPENAI_API_KEY and ai_config.OPENAI_BASE_URL else 1
    reasons = await asyncio.to_thread(
        generate_summary, raw_options, user_context, baseline=baseline_ctx, retries=retries
    )
    enriched = {o["tier"]: o for o in _enrich_options(raw_options, user_context, baseline_ctx)}

    options = []
    for raw in raw_options:
        e = enriched[raw["tier"]]
        options.append(
            PortfolioOptionOut(
                **raw,
                reason=reasons[raw["tier"]],
                extra_vs_baseline=e["extra_vs_baseline"],
                extra_vs_simple=e["extra_vs_simple"],
                new_bank_count=len(e["new_banks"]),
                required_actions=e["required_actions"],
            )
        )
    return options, baseline


def _holding_conditions(alloc: Allocation) -> list[UserHoldingCondition]:
    """보유 건마다 조건 종류는 한 번만 남길 수 있어(UNIQUE) 같은 종류는 우대폭을 합친다."""
    by_type: dict[str, UserHoldingCondition] = {}
    for applied in alloc.applied:
        cond = applied.condition
        row = by_type.get(cond.condition_type)
        if row is None:
            by_type[cond.condition_type] = UserHoldingCondition(
                condition_id=cond.condition_id,
                condition_type=cond.condition_type,
                rate_bonus=applied.rate_bonus,
                evidence_text=cond.evidence_text,
            )
        else:
            row.rate_bonus += applied.rate_bonus
    return list(by_type.values())


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

    numbers = _calc(allocations, _tax_context(profile, today))
    for kind, allocs in (("deposit", allocations.deposit_allocs), ("installment", allocations.installment_allocs)):
        for alloc in allocs:
            session.add(
                UserHolding(
                    portfolio_id=portfolio.portfolio_id,
                    option_id=alloc.option.option_id,
                    institution=alloc.institution_name,
                    product_name=alloc.product.product_name,
                    amount=alloc.amount if kind == "deposit" else None,
                    monthly_amount=alloc.amount if kind == "installment" else None,
                    base_rate=alloc.option.base_rate,
                    effective_rate=alloc.effective_rate,
                    max_rate=alloc.option.max_rate,
                    start_date=today,
                    maturity_date=_add_months(today, alloc.option.period_months),
                    applied_conditions=_holding_conditions(alloc),
                )
            )

    portfolio.after_tax_total = numbers.after_tax_total
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
