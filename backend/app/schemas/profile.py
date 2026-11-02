"""프로필 요청/응답 스키마.

STEP2·3 답변은 앱(frontend/lib/models/onboarding_input.dart)이 들고 있는 값을 **선택지 문구 그대로** 받는다.
필드 이름도 앱 필드를 snake_case 로 옮긴 것이다. 문구를 DB 값으로 해석하는 규칙은 services/onboarding.py.
선택지에 없는 문구는 422 로 거절한다 - 앱 문구가 바뀌었는데 조용히 '모름'으로 처리되면 우대금리가 빠져도 모른다.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.services.onboarding import (
    BANK_LABELS,
    CARD_SPENDING_LABELS,
    ELIGIBLE_LABELS,
    JOIN_CHOICE_LABELS,
    MEMBERSHIP_LABELS,
    SOCIAL_LABELS,
    TAX_EXEMPT_LABELS,
    YES_NO_LABELS,
)

BankLabel = Literal[BANK_LABELS]
YesNo = Literal[YES_NO_LABELS]


class ProfileCreate(BaseModel):
    user_id: int | None = Field(default=None, description="없으면 익명 사용자를 새로 만든다")

    # STEP1 - 금액은 원 단위
    lump_sum: int = Field(default=0, ge=0)
    monthly_saving: int = Field(default=0, ge=0)
    period_months: int = Field(gt=0)

    # STEP2 - 전부 선택. 안 보내면 '모름'으로 계산한다 (혜택을 부풀리지 않는 쪽)
    current_banks: list[BankLabel] = Field(default_factory=list, description="현재 보유 중인 계좌의 은행 (복수)")
    main_bank: BankLabel | None = Field(default=None, description="주 거래은행")
    birth_date: date | None = Field(default=None, description="생년월일 (YYYY-MM-DD)")
    salary_account_transferable: YesNo | None = Field(default=None, description="급여 받는 계좌를 옮길 수 있나요?")
    auto_transfer_movable: YesNo | None = Field(default=None, description="통신비·공과금 자동이체를 옮기실 수 있나요?")
    savings_auto_transfer_possible: YesNo | None = Field(default=None, description="적금상품 자동이체가 가능하신가요?")
    pension_account_transferable: YesNo | None = Field(default=None, description="연금수령 계좌를 옮기실 수 있나요?")
    cooperative_insurance_join_status: YesNo | None = Field(
        default=None, description="공제(새마을금고, 신협 등) 가입 실적이 있으시거나, 가입 의사가 있으신가요?"
    )
    monthly_card_spending: Literal[CARD_SPENDING_LABELS] | None = Field(
        default=None, description="매 달 카드를 얼마나 쓰시나요?"
    )
    marketing_consent: YesNo | None = Field(default=None, description="마케팅 정보 수신에 동의하실 수 있나요?")
    can_install_bank_app: YesNo | None = Field(default=None, description="해당 은행 앱을 설치해서 쓰실 수 있나요?")
    tax_exempt_eligibility: list[Literal[TAX_EXEMPT_LABELS]] = Field(
        default_factory=list, description="비과세종합저축 해당 항목 (복수)"
    )
    special_household_types: list[Literal[SOCIAL_LABELS]] = Field(
        default_factory=list, description="다자녀·한부모 등 해당 항목 (복수)"
    )

    # STEP3 - 신협·새마을금고 조합 예탁금 세금 감면 판정용. 대화 분기에 따라 일부만 온다
    cooperative_membership_status: Literal[MEMBERSHIP_LABELS] | None = Field(
        default=None, description="혹시 조합원으로 가입되어 있으실까요?"
    )
    cooperative_join_choices: list[Literal[JOIN_CHOICE_LABELS]] = Field(
        default_factory=list, description="가입을 고려해보실 수 있는 곳 (복수)"
    )
    mutual_finance_tax_exempt_eligible: Literal[ELIGIBLE_LABELS] | None = Field(
        default=None, description="총급여 7,000만원 이하에 해당되시나요?"
    )
    mutual_finance_existing_amount: int | None = Field(
        default=None, ge=0, description="다른 곳에 비과세로 넣어둔 돈(원). '잘 모르겠어요'면 null"
    )
    additional_note: str | None = Field(default=None, max_length=2000, description="자유 입력 메모")


class ProfileOut(BaseModel):
    model_config = {"from_attributes": True}

    profile_id: int
    user_id: int
    capital: int
    monthly_saving: int
    period_months: int
    main_bank_code: str | None
    held_bank_codes: list[str]
    accepts_membership: bool | None
    coop_tax_eligible: bool | None
    coop_exempt_used: int | None
    created_at: datetime
