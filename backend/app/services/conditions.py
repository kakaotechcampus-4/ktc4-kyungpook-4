"""우대조건 판정 - 티어마다 어떤 우대조건을 '받는다'고 볼지 정하고 실효금리를 계산한다.

[티어별로 인정하는 조건 - 2026-10-13 기획 확정안 기준]
  단순형 : 이미 충족한 조건만. 사실로 판정할 수 있는 것뿐이다.
           주거래은행(그 은행이 사용자의 주거래은행) / 신규고객(처음 거래하는 기관)
  균형형 : 단순형 + 약간의 행동 변화. 가입할 때 한 번 하면 되는 일과 자동이체.
           마케팅동의(동의한다고 답한 경우) / 비대면가입(앱 설치 못 한다고 답하지 않은 경우)
           / 자동이체(옮길 수 없다고 답하지 않은 경우)
  최대형 : 모든 우대조건 달성을 가정. 급여이체·카드실적·공과금이체·공제가입·연금수령·기타 포함.
  안정형 : 균형형과 같은 범위 (1금융만 쓰는 다른 축의 안이라 조건 범위는 균형형을 따른다).
  단일형 : 단순형과 같은 범위 (주거래은행 상품 하나에 그대로 넣는 기준선).

연령조건은 어느 티어에서도 인정하지 않는다 - 행동으로 채우는 조건이 아니라 자격이고,
원문에 나이 기준이 거의 없어(210건 중 7건) 판정할 수 없다.
우대폭(rate_bonus)이 원문에 없는 조건은 가산할 수 없어 뺀다.

실효금리 = min(기본금리 + 인정된 우대폭 합, 최고금리). 같은 exclusive_group 은 가장 큰 것 하나만.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import IntEnum

from app.models.product import ProductCondition, ProductOption
from app.models.profile import UserProfile


class Scope(IntEnum):
    SIMPLE = 1
    BALANCED = 2
    MAX = 3


# 조건 종류 -> 이 조건을 인정하기 시작하는 범위 (판정이 사용자 답변에 달린 것은 아래 _counts 에서 따로 본다)
_LIGHT_ACTIONS = ("마케팅동의", "비대면가입", "자동이체")
_NEVER = ("연령조건",)

# DB 단위(enums.THRESHOLD_UNITS) -> 사용자에게 보여줄 단위
_UNIT_LABEL = {
    "COUNT": "회",
    "MONTH": "개월",
    "WEEK": "주",
    "DAY": "일",
    "HOUR": "시간",
    "AGE": "세",
    "SCORE": "점",
    "STEP": "단계",
}


@dataclass
class AppliedCondition:
    condition: ProductCondition
    rate_bonus: Decimal  # 실제로 가산한 %p. 최고금리 상한에 걸리면 원래 우대폭보다 작다
    already_met: bool

    def to_out(self) -> dict:
        """AI Summary 가 기대하는 applied_conditions 한 줄 (ktc4_ai.summary 모듈 docstring)."""
        value, unit = self.condition.threshold_value, self.condition.threshold_unit
        if unit == "KRW" and value is not None:
            value, unit = (value // 10_000, "만원") if value % 10_000 == 0 else (value, "원")
        elif unit is not None:
            unit = _UNIT_LABEL.get(unit, unit)
        return {
            "condition_type": self.condition.condition_type,
            "bonus_rate": float(self.rate_bonus),
            "threshold_value": value,
            "threshold_unit": unit,
            "already_met": self.already_met,
        }


def _already_met(cond: ProductCondition, is_main_bank: bool, is_new_institution: bool) -> bool:
    if cond.condition_type == "주거래은행":
        return is_main_bank
    if cond.condition_type == "신규고객":
        return is_new_institution
    return False


def _counts(cond: ProductCondition, scope: Scope, profile: UserProfile, already_met: bool) -> bool:
    ctype = cond.condition_type
    if ctype in _NEVER or cond.rate_bonus is None:
        return False
    if already_met:
        return True
    if ctype in ("주거래은행", "신규고객"):
        # 사실로 정해지는 조건이라 행동으로 채울 수 없다. 최대형만 '달성 가정'으로 인정한다
        return scope >= Scope.MAX and ctype == "주거래은행"
    if scope >= Scope.MAX:
        return True
    if scope >= Scope.BALANCED and ctype in _LIGHT_ACTIONS:
        if ctype == "마케팅동의":
            return profile.marketing_consent is True
        if ctype == "비대면가입":
            return profile.app_install is not False
        return profile.auto_transfer is not False
    return False


def _applies_to_period(cond: ProductCondition, period_months: int) -> bool:
    low, high = cond.applies_period_min, cond.applies_period_max
    return (low is None or period_months >= low) and (high is None or period_months <= high)


def evaluate(
    option: ProductOption,
    conditions: list[ProductCondition],
    scope: Scope,
    profile: UserProfile,
    *,
    is_main_bank: bool,
    is_new_institution: bool,
) -> tuple[Decimal, list[AppliedCondition]]:
    """이 범위에서 받는다고 보는 우대조건과 그 결과 실효금리를 돌려준다."""
    picked: list[AppliedCondition] = []
    best_in_group: dict[str, AppliedCondition] = {}
    for cond in conditions:
        if not _applies_to_period(cond, option.period_months):
            continue
        met = _already_met(cond, is_main_bank, is_new_institution)
        if not _counts(cond, scope, profile, met):
            continue
        applied = AppliedCondition(condition=cond, rate_bonus=cond.rate_bonus, already_met=met)
        if cond.exclusive_group:
            current = best_in_group.get(cond.exclusive_group)
            if current is None or applied.rate_bonus > current.rate_bonus:
                best_in_group[cond.exclusive_group] = applied
        else:
            picked.append(applied)
    picked.extend(best_in_group.values())

    # 최고금리를 넘으면 우대폭을 큰 것부터 남기고 뒤쪽을 깎는다 (가산 합 = 실효금리 - 기본금리 가 되게)
    picked.sort(key=lambda a: a.rate_bonus, reverse=True)
    room = option.max_rate - option.base_rate
    for applied in picked:
        applied.rate_bonus = min(applied.rate_bonus, max(room, Decimal("0")))
        room -= applied.rate_bonus
    picked = [a for a in picked if a.rate_bonus > 0]
    return option.base_rate + sum((a.rate_bonus for a in picked), Decimal("0")), picked
