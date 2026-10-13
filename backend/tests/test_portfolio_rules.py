"""우대조건 판정(services/conditions.py)과 티어 배분 규칙(services/portfolio.py). DB 없이 돈다."""

from decimal import Decimal
from types import SimpleNamespace

from app.services.conditions import Scope, evaluate
from app.services.portfolio import (
    DEPOSIT_PROTECTION_LIMIT,
    TIER_SPECS,
    Candidate,
    _allocate_greedy,
    _BankInfo,
    _rank,
    _TierState,
)
from app.services.tax import TaxContext

SPEC = {s.name: s for s in TIER_SPECS}


def _profile(**kw):
    base = {"marketing_consent": False, "app_install": None, "auto_transfer": None, "accepts_membership": None}
    return SimpleNamespace(**(base | kw))


def _option(base="3.00", max_="5.00", period=12):
    return SimpleNamespace(base_rate=Decimal(base), max_rate=Decimal(max_), period_months=period)


def _cond(ctype, bonus="0.50", group=None, pmin=None, pmax=None, value=None, unit=None):
    return SimpleNamespace(
        condition_type=ctype,
        rate_bonus=None if bonus is None else Decimal(bonus),
        exclusive_group=group,
        applies_period_min=pmin,
        applies_period_max=pmax,
        threshold_value=value,
        threshold_unit=unit,
    )


def _eval(conds, scope, profile=None, *, main=False, new=False, option=None):
    return evaluate(option or _option(), conds, scope, profile or _profile(), is_main_bank=main, is_new_institution=new)


# --- 우대조건 범위 -----------------------------------------------------------


def test_simple_counts_only_facts():
    conds = [_cond("주거래은행"), _cond("신규고객"), _cond("자동이체"), _cond("급여이체")]
    rate, applied = _eval(conds, Scope.SIMPLE, main=True, new=True)
    assert rate == Decimal("4.00")
    assert {a.condition.condition_type for a in applied} == {"주거래은행", "신규고객"}
    assert all(a.already_met for a in applied)


def test_balanced_adds_light_actions_by_answers():
    conds = [_cond("마케팅동의"), _cond("비대면가입"), _cond("자동이체"), _cond("급여이체")]
    _, applied = _eval(conds, Scope.BALANCED, _profile(marketing_consent=True))
    assert {a.condition.condition_type for a in applied} == {"마케팅동의", "비대면가입", "자동이체"}
    assert not any(a.already_met for a in applied)

    _, applied = _eval(conds, Scope.BALANCED, _profile(app_install=False, auto_transfer=False))
    assert applied == []  # 마케팅 미동의 + 앱 설치 불가 + 자동이체 불가


def test_max_assumes_everything_but_age_and_missing_bonus():
    conds = [_cond("급여이체"), _cond("카드실적"), _cond("기타", "0.30"), _cond("연령조건"), _cond("공제가입", None)]
    rate, applied = _eval(conds, Scope.MAX)
    assert rate == Decimal("4.30")
    assert {a.condition.condition_type for a in applied} == {"급여이체", "카드실적", "기타"}


def test_rate_is_capped_at_max_rate():
    conds = [_cond("급여이체", "1.50"), _cond("카드실적", "1.00")]
    rate, applied = _eval(conds, Scope.MAX, option=_option("3.00", "4.00"))
    assert rate == Decimal("4.00")
    assert [a.rate_bonus for a in applied] == [Decimal("1.00")]  # 큰 것부터 남기고 나머지는 깎여 사라짐


def test_exclusive_group_takes_best_only():
    conds = [_cond("카드실적", "0.20", group="g1"), _cond("카드실적", "0.50", group="g1")]
    rate, _ = _eval(conds, Scope.MAX)
    assert rate == Decimal("3.50")


def test_condition_outside_period_is_ignored():
    rate, _ = _eval([_cond("급여이체", pmin=24)], Scope.MAX, option=_option(period=12))
    assert rate == Decimal("3.00")


def test_threshold_is_shown_in_user_units():
    _, applied = _eval([_cond("카드실적", value=300_000, unit="KRW")], Scope.MAX)
    out = applied[0].to_out()
    assert (out["threshold_value"], out["threshold_unit"]) == (30, "만원")


# --- 티어 배분 -------------------------------------------------------------


def _cand(code, base, *, pid=None, itype="은행", cap=None, conds=()):
    product = SimpleNamespace(
        product_id=pid or f"{code}-P", institution_code=code, amount_cap=cap, monthly_cap=None, product_name=pid or code
    )
    return Candidate(product, _option(base, "9.00"), code, itype, list(conds))


def _alloc(total, cands, tier, banks, profile=None, tax=None):
    profile = profile or _profile()
    tax = tax or TaxContext.for_profile(2026, None, None, None)
    ranked = _rank(cands, SPEC[tier], profile, banks, tax)
    return _allocate_greedy(total, ranked, "amount_cap", SPEC[tier], banks, _TierState())


BANKS = _BankInfo(main_bank_code="BANK-A", codes={"BANK-A", "BANK-B"})


def test_simple_uses_only_held_banks():
    cands = [_cand("BANK-A", "3.00"), _cand("BANK-NEW", "4.00"), _cand("CU-1", "5.00", itype="신협")]
    allocs = _alloc(10_000_000, cands, "단순형", BANKS)
    assert [a.product.institution_code for a in allocs] == ["BANK-A"]


def test_balanced_allows_one_new_institution():
    cands = [_cand("BANK-N1", "4.50", cap=5_000_000), _cand("BANK-N2", "4.40"), _cand("BANK-A", "3.00")]
    allocs = _alloc(10_000_000, cands, "균형형", BANKS)
    assert [a.product.institution_code for a in allocs] == ["BANK-N1", "BANK-A"]


def test_stable_uses_first_tier_banks_only():
    cands = [_cand("SB-1", "5.00", itype="저축은행"), _cand("BANK-N1", "3.50")]
    allocs = _alloc(10_000_000, cands, "안정형", BANKS)
    assert [a.product.institution_code for a in allocs] == ["BANK-N1"]


def test_deposit_protection_caps_each_institution():
    cands = [_cand("BANK-A", "4.00", pid="A1"), _cand("BANK-A", "3.90", pid="A2"), _cand("BANK-B", "3.00")]
    allocs = _alloc(150_000_000, cands, "최대형", BANKS)
    assert [(a.product.product_id, a.amount) for a in allocs] == [
        ("A1", DEPOSIT_PROTECTION_LIMIT),
        ("BANK-B-P", 50_000_000),  # 같은 은행 A2 는 한도가 남지 않아 건너뜀
    ]


def test_coop_tax_benefit_changes_ranking_for_members():
    cands = [_cand("BANK-N1", "4.00"), _cand("CU-1", "3.80", itype="신협")]
    member_tax = TaxContext.for_profile(2026, True, True, 0)
    member = _alloc(10_000_000, cands, "최대형", BANKS, tax=member_tax)
    non_member = _alloc(10_000_000, cands, "최대형", BANKS)
    assert member[0].product.institution_code == "CU-1"  # 3.80 x (1-1.4%) > 4.00 x (1-15.4%)
    assert non_member[0].product.institution_code == "BANK-N1"


def test_unknown_banks_do_not_limit_new_institutions():
    unknown = _BankInfo(main_bank_code=None, codes=set())
    cands = [_cand("BANK-N1", "4.50", cap=5_000_000), _cand("BANK-N2", "4.40")]
    allocs = _alloc(10_000_000, cands, "균형형", unknown)
    assert len(allocs) == 2


def test_overflow_spreads_to_next_product_instead_of_breaking_protection():
    cands = [_cand("BANK-A", "4.00"), _cand("BANK-B", "3.00")]
    allocs = _alloc(150_000_000, cands, "단순형", BANKS)
    assert [a.amount for a in allocs] == [DEPOSIT_PROTECTION_LIMIT, 50_000_000]


def test_coop_excluded_when_membership_refused():
    cands = [_cand("CU-1", "5.00", itype="신협"), _cand("BANK-N1", "3.00")]
    refused = _alloc(10_000_000, cands, "최대형", BANKS, profile=_profile(accepts_membership=False))
    unknown = _alloc(10_000_000, cands, "최대형", BANKS)
    assert [a.product.institution_code for a in refused] == ["BANK-N1"]
    assert [a.product.institution_code for a in unknown] == ["CU-1"]
