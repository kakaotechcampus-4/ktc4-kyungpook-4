"""세금 계산 규칙 (app/services/tax.py). DB 없이 돈다."""

from decimal import Decimal

import pytest

from app.services.tax import COOP_EXEMPT_LIMIT, TaxContext, coop_rate

BANK = "BANK-0010001"
COOP = "KFCC-0001"


@pytest.mark.parametrize(
    ("join_year", "low_income", "expected"),
    [
        (2026, True, "0.014"),  # 비과세 - 농어촌특별세 1.4% 만
        (2028, True, "0.014"),
        (2029, True, "0.059"),  # 5% + 농특세 (14-5)*10% = 0.9%
        (2030, True, "0.095"),  # 9% + 농특세 0.5%
        (2026, False, "0.059"),
        (2027, False, "0.095"),
    ],
)
def test_coop_rate_by_join_year_and_income(join_year, low_income, expected):
    assert coop_rate(join_year, low_income) == Decimal(expected)


def _ctx(**kw) -> TaxContext:
    args = {"join_year": 2026, "accepts_membership": True, "coop_tax_eligible": True, "coop_exempt_used": 0} | kw
    return TaxContext.for_profile(**args)


def test_bank_product_uses_general_rate():
    assert _ctx().after_tax(BANK, Decimal(1_000_000), principal=30_000_000).after_tax == 846_000


def test_coop_within_limit_is_exempt():
    assert _ctx().after_tax(COOP, Decimal(1_000_000), principal=30_000_000).after_tax == 986_000


def test_non_member_or_unknown_membership_pays_general_rate():
    assert _ctx(accepts_membership=False).after_tax(COOP, Decimal(1_000_000), principal=10_000_000).after_tax == 846_000
    assert _ctx(accepts_membership=None).after_tax(COOP, Decimal(1_000_000), principal=10_000_000).after_tax == 846_000


def test_unknown_income_is_treated_as_high_income():
    assert _ctx(coop_tax_eligible=None).after_tax(COOP, Decimal(1_000_000), principal=10_000_000).after_tax == 941_000


def test_amount_over_limit_is_split():
    # 4천만원 중 3천만원(3/4)만 감면. 이자 100만원 → 75만원 1.4%, 25만원 15.4%
    assert _ctx().after_tax(COOP, Decimal(1_000_000), principal=40_000_000).after_tax == 739_500 + 211_500


def test_limit_is_shared_across_products_and_existing_deposits():
    ctx = _ctx(coop_exempt_used=10_000_000)  # 남은 한도 2천만원
    assert ctx.coop_room == 20_000_000
    assert ctx.after_tax(COOP, Decimal(1_000_000), principal=20_000_000).after_tax == 986_000
    assert ctx.after_tax(COOP, Decimal(1_000_000), principal=20_000_000).after_tax == 846_000  # 한도 소진
    assert ctx.coop_room == 0


def test_existing_deposit_over_limit_leaves_no_room():
    assert _ctx(coop_exempt_used=COOP_EXEMPT_LIMIT + 1).coop_room == 0


def test_tax_saving_and_general_interest():
    result = _ctx().after_tax(COOP, Decimal(1_000_000), principal=40_000_000)
    assert result.tax_saving == 951_000 - 846_000
    assert result.general_interest == Decimal(250_000)  # 한도 밖 1/4 만 일반과세
    assert _ctx().after_tax(BANK, Decimal(1_000_000), principal=1).tax_saving == 0
