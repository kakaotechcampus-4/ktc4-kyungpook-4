"""이자소득 세금 계산.

[일반] 소득세 14% + 지방소득세 1.4% = 15.4%.

[조합 예탁금] 조세특례제한법 제89조의3 (2025-12-02 국회 통과 개정 반영)
신협·새마을금고 조합원의 예탁금은 1인당 합계 3천만원까지 소득세가 감면된다. 세율은 **가입한 해**와
총급여 7천만원(종합소득 6천만원) 초과 여부로 갈린다.

    가입 연도     총급여 7천만원 이하   총급여 7천만원 초과
    2026          비과세                5%
    2027~2028     비과세                9%
    2029          5%                    9%
    2030~         9%                    9%

감면분에는 농어촌특별세가 붙는다 - 감면받은 소득세(14% - 적용세율)의 10%. 지방소득세는 없다.
그래서 실제 부담은 비과세 1.4% / 5% → 5.9% / 9% → 9.5% 다.
(농어민 조합원은 기준이 따로 있지만 입력으로 받지 않아 다루지 않는다.)
"""

from dataclasses import dataclass
from decimal import Decimal

GENERAL_RATE = Decimal("0.154")

COOP_EXEMPT_LIMIT = 30_000_000  # 조합 예탁금 감면 한도. 모든 조합 합산, 1인당
_INCOME_TAX = Decimal("0.14")
_RURAL_SPECIAL_TAX = Decimal("0.10")  # 감면세액에 붙는 농어촌특별세율

# 신협·새마을금고 institution_code 접두사. 조합 예탁금 감면 대상 기관이다.
COOP_CODE_PREFIXES = ("CU-", "KFCC-")


def is_coop(institution_code: str) -> bool:
    return institution_code.startswith(COOP_CODE_PREFIXES)


def _coop_income_tax(join_year: int, low_income: bool) -> Decimal:
    if low_income:
        if join_year <= 2028:
            return Decimal("0")
        return Decimal("0.05") if join_year == 2029 else Decimal("0.09")
    if join_year <= 2025:
        return Decimal("0")
    return Decimal("0.05") if join_year == 2026 else Decimal("0.09")


def coop_rate(join_year: int, low_income: bool) -> Decimal:
    """조합 예탁금 감면 한도 안쪽에 적용되는 실제 부담 세율 (농어촌특별세 포함)."""
    income_tax = _coop_income_tax(join_year, low_income)
    return income_tax + (_INCOME_TAX - income_tax) * _RURAL_SPECIAL_TAX


@dataclass
class TaxResult:
    after_tax: int  # 세후 이자(원)
    tax_saving: int  # 일반 15.4% 대비 줄어든 세금(원). 감면이 없으면 0
    general_interest: Decimal  # 일반과세된 세전 이자. 분리과세분은 금융소득종합과세 합산에서 빠진다


@dataclass
class TaxContext:
    """한 포트폴리오 안에서 조합 예탁금 감면 한도를 상품끼리 나눠 쓰기 위한 상태."""

    is_member: bool
    coop_rate: Decimal
    coop_room: int  # 남은 감면 한도(원)

    @classmethod
    def for_profile(
        cls,
        join_year: int,
        accepts_membership: bool | None,
        coop_tax_eligible: bool | None,
        coop_exempt_used: int | None,
    ) -> "TaxContext":
        # 모르는 값은 혜택을 부풀리지 않는 쪽으로 둔다: 조합원 여부 모름 = 아님, 소득 모름 = 7천만원 초과.
        # 이미 쓴 한도는 모르면 0 으로 본다 - 대부분의 사용자는 상호금융 예탁금이 없다.
        return cls(
            is_member=accepts_membership is True,
            coop_rate=coop_rate(join_year, coop_tax_eligible is True),
            coop_room=max(0, COOP_EXEMPT_LIMIT - (coop_exempt_used or 0)),
        )

    def after_tax(self, institution_code: str, interest: Decimal, principal: int) -> TaxResult:
        """세전 이자에서 세금을 뺀다. 조합 예탁금이면 남은 한도만큼만 감면 세율을 쓰고 한도를 줄인다.

        principal 은 한도 판정 기준 금액 - 예금은 원금, 적금은 만기까지의 총 납입액.
        한도를 일부만 쓰면 이자도 같은 비율로 나눈다 (단리라 이자가 원금에 비례한다).
        """
        general_after_tax = int((interest * (1 - GENERAL_RATE)).to_integral_value())
        if not (self.is_member and is_coop(institution_code)) or principal <= 0 or self.coop_room <= 0:
            return TaxResult(after_tax=general_after_tax, tax_saving=0, general_interest=interest)

        exempt_principal = min(principal, self.coop_room)
        self.coop_room -= exempt_principal
        exempt_interest = interest * exempt_principal / principal
        general_interest = interest - exempt_interest
        tax = exempt_interest * self.coop_rate + general_interest * GENERAL_RATE
        after_tax = int((interest - tax).to_integral_value())
        return TaxResult(
            after_tax=after_tax, tax_saving=after_tax - general_after_tax, general_interest=general_interest
        )

    def effective_rate(self, institution_code: str) -> Decimal:
        """후보 정렬용 세율 - 한도는 보지 않고 이 상품에 기대할 수 있는 세율."""
        if self.is_member and is_coop(institution_code) and self.coop_room > 0:
            return self.coop_rate
        return GENERAL_RATE
