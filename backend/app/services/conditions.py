"""우대조건 판정 - 티어마다 어떤 우대조건을 '받는다'고 볼지 정하고 실효금리를 계산한다.

[티어별로 인정하는 조건 - 2026-10-13 기획 확정안 기준]
  단순형 : 이미 충족한 조건만. 사실로 판정할 수 있는 것뿐이다.
           주거래은행(그 은행이 사용자의 주거래은행) / 신규고객(처음 거래하는 기관)
  균형형 : 단순형 + 약간의 행동 변화. 가입할 때 한 번 하면 되는 일과 자동이체.
           마케팅동의(동의한다고 답한 경우) / 비대면가입(앱 설치 못 한다고 답하지 않은 경우)
           / 자동이체(적금 자동이체 못 한다고 답하지 않은 경우)
           + STEP2 에서 '가능해요'라고 답한 조건: 급여이체·공과금이체·연금수령·공제가입
           + 카드실적: 월 카드 사용액이 실적 기준 이상인 경우 (쓰던 만큼 그 은행 카드로 옮기면 된다)
           + 기타: 챗봇에서 충족한다고 답한 조건
  최대형 : 모든 우대조건 달성을 가정. 급여이체·카드실적·공과금이체·공제가입·연금수령·기타 포함.
           단 '불가능해요'라고 답한 조건, 카드 사용액이 실적 기준에 못 미치는 카드실적,
           챗봇에서 미충족(모름 포함)으로 답한 기타 조건은 뺀다. 챗봇이 묻지 않은 기타 조건은 계속 가정한다.
  안정형 : 균형형과 같은 범위 (1금융만 쓰는 다른 축의 안이라 조건 범위는 균형형을 따른다).
  단일형 : 단순형과 같은 범위 (주거래은행 상품 하나에 그대로 넣는 기준선).

연령조건은 어느 티어에서도 인정하지 않는다 - 행동으로 채우는 조건이 아니라 자격이고,
원문에 나이 기준이 거의 없어(210건 중 7건) 판정할 수 없다.
우대폭(rate_bonus)이 원문에 없는 조건은 가산할 수 없어 뺀다.

실효금리 = min(기본금리 + 인정된 우대폭 합, 최고금리). 같은 exclusive_group 은 가장 큰 것 하나만.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import IntEnum

from app.models.product import ProductCondition, ProductOption
from app.models.profile import UserProfile


class Scope(IntEnum):
    SIMPLE = 1
    BALANCED = 2
    MAX = 3


# 답을 몰라도 균형형에서 인정하는 가벼운 행동 (가입할 때 한 번 하면 되는 일과 자동이체)
_LIGHT_ACTIONS = ("마케팅동의", "비대면가입", "자동이체")
_NEVER = ("연령조건",)

# 조건 종류 -> 그 조건을 채울 수 있는지 물어본 STEP2 답 (user_profile 컬럼).
# 자동이체 조건은 실측상 대부분 '적금 자동이체 납입'·'만기자동이체 등록'이라 적금 자동이체 질문에 묶는다.
_ANSWER_COLUMNS = {
    "급여이체": "salary_transfer",
    "공과금이체": "auto_transfer",
    "자동이체": "savings_auto_transfer",
    "연금수령": "pension_transfer",
    "공제가입": "coop_insurance",
    "비대면가입": "app_install",
}

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


def _card_scope(cond: ProductCondition, usage: int | None) -> Scope | None:
    """카드실적을 인정하기 시작하는 범위. None = 어느 티어에서도 인정하지 않음.
    실적 기준은 대부분 '월 N원 이상'이라 월 카드 사용액(구간 하한)과 바로 비교한다."""
    if usage is None:
        return Scope.MAX
    if cond.threshold_unit == "KRW" and cond.threshold_value is not None:
        # 지금 쓰는 만큼을 그 은행 카드로 옮기기만 하면 된다
        return Scope.BALANCED if usage >= cond.threshold_value else None
    # 기준 금액을 모르는 조건('1회 이상 사용' 등). 카드를 쓰는 사람만 최대형에서 인정한다
    return Scope.MAX if usage > 0 else None


def _answer_scope(cond: ProductCondition, profile: UserProfile, etc_answers: Mapping[str, bool]) -> Scope | None:
    """행동으로 채우는 조건을 인정하기 시작하는 범위. None = 어느 티어에서도 인정하지 않음."""
    ctype = cond.condition_type
    if ctype == "기타":
        # 상품마다 내용이 달라 STEP2 고정 문항으로 못 묻고, 챗봇이 조건별로 묻는다 (condition_id 로 찾는다)
        answer = etc_answers.get(cond.condition_id)
        if answer is True:
            return Scope.BALANCED
        if answer is False:
            return None  # 미충족(모름 포함)으로 답했다 - 최대형이라도 가정하지 않는다
        return Scope.MAX  # 챗봇이 묻지 않았다 - 지금처럼 최대형에서만 가정한다
    if ctype == "카드실적":
        return _card_scope(cond, profile.monthly_card_usage)
    if ctype == "마케팅동의":
        # 컬럼이 NOT NULL 이라 '모름'과 '불가'가 둘 다 False 로 저장된다. 그래서 최대형에서는 계속 가정한다
        return Scope.BALANCED if profile.marketing_consent is True else Scope.MAX
    column = _ANSWER_COLUMNS.get(ctype)
    if column is None:
        return Scope.MAX
    answer = getattr(profile, column)
    if answer is False:
        return None  # 본인이 못 한다고 답했다 - 최대형이라도 가정하지 않는다
    if answer is True or ctype in _LIGHT_ACTIONS:
        return Scope.BALANCED
    return Scope.MAX


def _counts(
    cond: ProductCondition,
    scope: Scope,
    profile: UserProfile,
    already_met: bool,
    etc_answers: Mapping[str, bool],
) -> bool:
    ctype = cond.condition_type
    if ctype in _NEVER or cond.rate_bonus is None:
        return False
    if already_met:
        return True
    if ctype in ("주거래은행", "신규고객"):
        # 사실로 정해지는 조건이라 행동으로 채울 수 없다. 최대형만 '달성 가정'으로 인정한다
        return scope >= Scope.MAX and ctype == "주거래은행"
    start = _answer_scope(cond, profile, etc_answers)
    return start is not None and scope >= start


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
    etc_answers: Mapping[str, bool] | None = None,
) -> tuple[Decimal, list[AppliedCondition]]:
    """이 범위에서 받는다고 보는 우대조건과 그 결과 실효금리를 돌려준다.

    etc_answers: 챗봇에서 받은 '기타' 조건 답 {condition_id: 충족 여부}. 없으면 아무것도 묻지 않은 것으로 본다.
    """
    etc_answers = etc_answers or {}
    picked: list[AppliedCondition] = []
    best_in_group: dict[str, AppliedCondition] = {}
    for cond in conditions:
        if not _applies_to_period(cond, option.period_months):
            continue
        met = _already_met(cond, is_main_bank, is_new_institution)
        if not _counts(cond, scope, profile, met, etc_answers):
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
