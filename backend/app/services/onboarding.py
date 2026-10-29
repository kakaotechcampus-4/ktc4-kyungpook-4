"""앱 STEP2·3 답변(선택지 문구)을 user_profile 컬럼 값으로 해석한다.

선택지 문구는 frontend/lib/screens/input/input_step2_screen.dart, input_step3_screen.dart,
frontend/lib/data/bank_options.dart 에서 그대로 옮겼다. 앱 문구가 바뀌면 여기도 같이 바꿔야 한다
(안 바꾸면 API 가 422 를 돌려줘서 바로 드러난다).

해석 원칙은 "틀린 숫자를 보여주느니 덜 보여준다" - 애매하면 None(모름)이나 우대금리를 덜 주는 쪽으로 둔다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.profile import ProfileCreate

# 앱 은행 선택지 -> institution_code. None 은 코드 하나로 정할 수 없는 선택지다.
#   신협·새마을금고 : 기관이 조합마다 따로라(1,800여 곳) 하나로 못 정한다. 조합은 어차피 항상
#                    신규 가입으로 보므로(portfolio._BankInfo.is_new) 보유 여부를 몰라도 계산이 같다.
#   우체국예금·씨티은행 : 금감원 공시 데이터에 없다 (상품도 없음).
BANK_CODES: dict[str, str | None] = {
    "국민은행": "BANK-0010927",
    "우리은행": "BANK-0010001",
    "IM뱅크(구. 대구은행)": "BANK-0010016",
    "새마을금고": None,
    "카카오뱅크": "BANK-0015130",
    "신한은행": "BANK-0011625",
    "하나은행": "BANK-0013909",
    "농협은행": "BANK-0013175",
    "기업은행": "BANK-0010026",
    "부산은행": "BANK-0010017",
    "광주은행": "BANK-0010019",
    "전북은행": "BANK-0010022",
    "경남은행": "BANK-0010024",
    "제주은행": "BANK-0010020",
    "신협": None,
    "우체국예금": None,
    "케이뱅크": "BANK-0014674",
    "토스뱅크": "BANK-0017801",
    "SC제일은행": "BANK-0010002",
    "씨티은행": None,
}

YES_NO: dict[str, bool | None] = {"가능해요": True, "잘 모르겠어요": None, "불가능해요": False}

# 구간의 하한(원)을 쓴다. 카드실적 우대를 부풀리지 않기 위해서다. 원문은 answers 에 남는다.
CARD_SPENDING: dict[str, int | None] = {
    "카드 안써요": 0,
    "30만원 미만": 0,
    "30~50만원": 300_000,
    "50~100만원": 500_000,
    "100만원 이상": 1_000_000,
    "잘 모르겠어요": None,
}

# 값은 enums.TAX_EXEMPT_CATEGORIES / SOCIAL_CARE_CATEGORIES. None = '해당없음'
TAX_EXEMPT: dict[str, str | None] = {
    "만 65세 이상이고 기초연금을 받고 있어요": "65세이상",
    "등록 장애인이에요": "장애인",
    "독립유공자/국가유공자예요": "유공자",
    "기초생활수급자예요": "기초생활수급자",
    "해당없음": None,
}
SOCIAL: dict[str, str | None] = {
    "다자녀 가정": "다자녀",
    "한부모 가정": "한부모",
    "다문화 가정": "다문화",
    "신혼부부": "신혼부부",
    "북한이탈주민(탈북자)": "탈북자",
    "해당없음": None,
}

MEMBER = "네,조합원이에요"
MEMBERSHIP_LABELS = (MEMBER, "잘 모르겠어요", "계좌만 있어요")

# 신협·새마을금고만 DB 에 예탁금 상품이 있다. 농협·수협 조합은 공시 데이터에 없어 골라도 후보가 안 생긴다.
JOIN_COOP = ("신협 (전국 어디든 가입 가능)", "새마을금고 (거주지·직장 지역만 가능)")
JOIN_CHOICE_LABELS = (*JOIN_COOP, "농협·수협 (출자금이 조금 더 높아요 (10만원 안팍))", "다 부담스러워요")

ELIGIBLE: dict[str, bool | None] = {"네,해당돼요": True, "잘 모르겠어요": None, "해당되지 않아요": False}

BANK_LABELS = tuple(BANK_CODES)
YES_NO_LABELS = tuple(YES_NO)
CARD_SPENDING_LABELS = tuple(CARD_SPENDING)
TAX_EXEMPT_LABELS = tuple(TAX_EXEMPT)
SOCIAL_LABELS = tuple(SOCIAL)
ELIGIBLE_LABELS = tuple(ELIGIBLE)

_STEP23_FIELDS = (
    "current_banks",
    "main_bank",
    "birth_date",
    "salary_account_transferable",
    "auto_transfer_movable",
    "savings_auto_transfer_possible",
    "pension_account_transferable",
    "cooperative_insurance_join_status",
    "monthly_card_spending",
    "marketing_consent",
    "can_install_bank_app",
    "tax_exempt_eligibility",
    "special_household_types",
    "cooperative_membership_status",
    "cooperative_join_choices",
    "mutual_finance_tax_exempt_eligible",
    "mutual_finance_existing_amount",
    "additional_note",
)


@dataclass
class Interpreted:
    """user_profile 과 하위 테이블에 넣을 값."""

    main_bank_code: str | None = None
    held_bank_codes: list[str] = field(default_factory=list)
    birth_date: date | None = None
    salary_transfer: bool | None = None
    auto_transfer: bool | None = None
    savings_auto_transfer: bool | None = None
    pension_transfer: bool | None = None
    coop_insurance: bool | None = None
    monthly_card_usage: int | None = None
    marketing_consent: bool | None = None
    app_install: bool | None = None
    accepts_membership: bool | None = None
    coop_tax_eligible: bool | None = None
    coop_exempt_used: int | None = None
    tax_exempt_categories: list[str] = field(default_factory=list)
    social_categories: list[str] = field(default_factory=list)
    answers: dict | None = None


def _yes_no(label: str | None) -> bool | None:
    return None if label is None else YES_NO[label]


def _mapped(labels: list[str], table: dict[str, str | None]) -> list[str]:
    """None('해당없음' 등)을 빼고 순서를 지켜 중복을 없앤다."""
    return list(dict.fromkeys(v for label in labels if (v := table[label]) is not None))


def _accepts_membership(status: str | None, join_choices: list[str]) -> bool | None:
    """신협·새마을금고 예탁금을 후보에 넣어도 되는지.

    True  : 이미 조합원이거나, 신협·새마을금고 중 가입할 수 있는 곳을 골랐다
    False : 가입할 곳을 골랐는데 신협·새마을금고는 없다 ('다 부담스러워요' 또는 농협·수협만)
    None  : 대화가 거기까지 안 갔다
    """
    if status == MEMBER:
        return True
    if any(choice in JOIN_COOP for choice in join_choices):
        return True
    if join_choices:
        return False
    return None


def interpret(body: ProfileCreate) -> Interpreted:
    main_bank_code = BANK_CODES[body.main_bank] if body.main_bank else None
    answers = body.model_dump(mode="json", include=set(_STEP23_FIELDS), exclude_defaults=True)
    return Interpreted(
        main_bank_code=main_bank_code,
        held_bank_codes=_mapped(body.current_banks, BANK_CODES),
        birth_date=body.birth_date,
        salary_transfer=_yes_no(body.salary_account_transferable),
        auto_transfer=_yes_no(body.auto_transfer_movable),
        savings_auto_transfer=_yes_no(body.savings_auto_transfer_possible),
        pension_transfer=_yes_no(body.pension_account_transferable),
        coop_insurance=_yes_no(body.cooperative_insurance_join_status),
        monthly_card_usage=CARD_SPENDING[body.monthly_card_spending] if body.monthly_card_spending else None,
        marketing_consent=_yes_no(body.marketing_consent),
        app_install=_yes_no(body.can_install_bank_app),
        accepts_membership=_accepts_membership(body.cooperative_membership_status, body.cooperative_join_choices),
        coop_tax_eligible=(
            ELIGIBLE[body.mutual_finance_tax_exempt_eligible] if body.mutual_finance_tax_exempt_eligible else None
        ),
        coop_exempt_used=body.mutual_finance_existing_amount,
        tax_exempt_categories=_mapped(body.tax_exempt_eligibility, TAX_EXEMPT),
        social_categories=_mapped(body.special_household_types, SOCIAL),
        answers=answers or None,
    )
