"""앱 STEP2·3 답변 해석 규칙 (app/services/onboarding.py). DB 없이 돈다."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.models.enums import SOCIAL_CARE_CATEGORIES, TAX_EXEMPT_CATEGORIES
from app.schemas.profile import ProfileCreate
from app.services.onboarding import SOCIAL, TAX_EXEMPT, interpret


def _body(**kw) -> ProfileCreate:
    return ProfileCreate(lump_sum=10_000_000, monthly_saving=500_000, period_months=12, **kw)


def test_step1_only_leaves_everything_unknown():
    parsed = interpret(_body())
    assert parsed.main_bank_code is None
    assert parsed.held_bank_codes == []
    assert parsed.salary_transfer is None
    assert parsed.accepts_membership is None
    assert parsed.answers is None


def test_full_step2_answers():
    parsed = interpret(
        _body(
            current_banks=["국민은행", "신협", "IM뱅크(구. 대구은행)", "우체국예금", "국민은행"],
            main_bank="국민은행",
            birth_date="1995-03-02",
            salary_account_transferable="가능해요",
            auto_transfer_movable="불가능해요",
            savings_auto_transfer_possible="가능해요",
            pension_account_transferable="잘 모르겠어요",
            cooperative_insurance_join_status="불가능해요",
            monthly_card_spending="30~50만원",
            marketing_consent="가능해요",
            can_install_bank_app="잘 모르겠어요",
            tax_exempt_eligibility=["해당없음"],
            special_household_types=["신혼부부", "북한이탈주민(탈북자)"],
        )
    )
    # 신협·우체국은 코드 하나로 못 정해서 빠지고, 중복은 한 번만
    assert parsed.held_bank_codes == ["BANK-0010927", "BANK-0010016"]
    assert parsed.main_bank_code == "BANK-0010927"
    assert parsed.birth_date == date(1995, 3, 2)
    assert (parsed.salary_transfer, parsed.auto_transfer) == (True, False)
    assert (parsed.savings_auto_transfer, parsed.pension_transfer, parsed.coop_insurance) == (True, None, False)
    assert parsed.monthly_card_usage == 300_000  # 구간 하한
    assert (parsed.marketing_consent, parsed.app_install) == (True, None)
    assert parsed.tax_exempt_categories == []
    assert parsed.social_categories == ["신혼부부", "탈북자"]
    # 원문은 보낸 그대로 남는다
    assert parsed.answers["monthly_card_spending"] == "30~50만원"
    assert parsed.answers["birth_date"] == "1995-03-02"


@pytest.mark.parametrize("main_bank", ["신협", "새마을금고", "씨티은행"])
def test_main_bank_without_single_code_is_unknown(main_bank):
    assert interpret(_body(main_bank=main_bank)).main_bank_code is None


@pytest.mark.parametrize(
    ("status", "choices", "expected"),
    [
        ("네,조합원이에요", [], True),
        ("계좌만 있어요", ["새마을금고 (거주지·직장 지역만 가능)"], True),
        (None, ["신협 (전국 어디든 가입 가능)", "농협·수협 (출자금이 조금 더 높아요 (10만원 안팍))"], True),
        (None, ["다 부담스러워요"], False),
        (None, ["농협·수협 (출자금이 조금 더 높아요 (10만원 안팍))"], False),  # DB 에 농협·수협 조합 상품이 없다
        ("잘 모르겠어요", [], None),
        (None, [], None),
    ],
)
def test_accepts_membership(status, choices, expected):
    parsed = interpret(_body(cooperative_membership_status=status, cooperative_join_choices=choices))
    assert parsed.accepts_membership is expected


def test_step3_tax_answers():
    parsed = interpret(
        _body(mutual_finance_tax_exempt_eligible="해당되지 않아요", mutual_finance_existing_amount=5_000_000)
    )
    assert parsed.coop_tax_eligible is False
    assert parsed.coop_exempt_used == 5_000_000


def test_unknown_label_is_rejected():
    with pytest.raises(ValidationError):
        _body(salary_account_transferable="네")
    with pytest.raises(ValidationError):
        _body(current_banks=["없는은행"])


def test_category_maps_stay_inside_db_check():
    """매핑 결과가 DB CHECK 목록 밖이면 INSERT 가 터진다."""
    assert {v for v in TAX_EXEMPT.values() if v} == set(TAX_EXEMPT_CATEGORIES)
    assert {v for v in SOCIAL.values() if v} == set(SOCIAL_CARE_CATEGORIES)
