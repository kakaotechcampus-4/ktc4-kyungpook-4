"""단일형(baseline): 예금·적금 중 하나만 고르고, 티어와는 같은 종류끼리 비교한다. DB 없이 돈다."""

from decimal import Decimal
from types import SimpleNamespace

from ktc4_ai.summary import _enrich_options

from app.services.portfolio import Allocation, TierAllocations, _calc, _pick_single_kind
from app.services.tax import TaxContext


def _tax():
    return TaxContext.for_profile(
        join_year=2026, accepts_membership=None, coop_tax_eligible=None, coop_exempt_used=None
    )


def _alloc(product_type, amount, rate, months=36):
    product = SimpleNamespace(
        product_id=f"BANK-1-{product_type}",
        institution_code="BANK-1",
        product_name=f"국민 {product_type}",
        product_type=product_type,
    )
    option = SimpleNamespace(period_months=months, base_rate=Decimal(rate))
    return Allocation(product, option, "국민은행", amount, Decimal(rate))


def _deposit(amount=100_000_000, rate="2.4"):
    return TierAllocations(36, [_alloc("예금", amount, rate)], [])


def _installment(monthly=500_000, rate="3.05"):
    return TierAllocations(36, [], [_alloc("적금", monthly, rate)])


def test_picks_kind_with_larger_after_tax_interest():
    # 1억 예금 세후 6,091,200원 vs 월 50만 적금 세후 716,033원 -> 예금
    picked, note = _pick_single_kind([(_deposit(), None), (_installment(), "기간 안내")], _tax)
    assert picked.deposit_allocs and not picked.installment_allocs
    assert note is None

    # 목돈이 작으면 적금이 이긴다: 100만 예금 vs 월 50만 적금
    picked, note = _pick_single_kind([(_deposit(amount=1_000_000), None), (_installment(), "기간 안내")], _tax)
    assert picked.installment_allocs and not picked.deposit_allocs
    assert note == "기간 안내"


def test_single_kind_when_only_one_is_available():
    picked, _ = _pick_single_kind([(_installment(), None)], _tax)
    assert picked.installment_allocs
    assert _pick_single_kind([], _tax) is None


def test_products_carry_product_type():
    numbers = _calc(
        TierAllocations(36, [_alloc("예금", 100_000_000, "2.4")], [_alloc("적금", 500_000, "3.05")]), _tax()
    )
    assert [p.product_type for p in numbers.products] == ["예금", "적금"]
    assert [p.after_tax_interest for p in numbers.products] == [6_091_200, 716_033]


def test_extra_vs_baseline_compares_same_kind_only():
    tier = {
        "tier": "단순형",
        "products": [
            {"product_type": "예금", "after_tax_interest": 7_000_000},
            {"product_type": "적금", "after_tax_interest": 800_000},
        ],
        "after_tax_total": 7_800_000,
    }
    baseline = {"product_type": "예금", "after_tax_total": 6_091_200}
    [enriched] = _enrich_options([tier], None, baseline)
    # 적금 이자 80만원은 단일형에 없는 돈이라 '더 받는 돈'에 넣지 않는다
    assert enriched["extra_vs_baseline"] == 7_000_000 - 6_091_200

    # product_type 이 없는 예전 형식이면 지금처럼 총액으로 비교한다
    [legacy] = _enrich_options([tier], None, {"after_tax_total": 6_091_200})
    assert legacy["extra_vs_baseline"] == 7_800_000 - 6_091_200
