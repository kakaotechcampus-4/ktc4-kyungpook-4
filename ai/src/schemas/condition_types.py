"""우대조건 분류 체계 - AI 프롬프트와 스키마가 공통으로 참조하는 단일 소스.

새 condition_type을 추가하려면 CONDITION_TYPE_DEFINITIONS에 항목을 추가한다.
- 프롬프트의 카테고리 목록, 보충 설명, '위 N개' 카운트가 자동으로 반영된다.
- DEFAULT_CONDITION_TYPE은 반드시 마지막 항목이어야 한다.
"""

# (타입값, 프롬프트 보충 설명) — 설명이 없으면 None
# 순서 = AI 프롬프트에 나열되는 순서
CONDITION_TYPE_DEFINITIONS: tuple[tuple[str, str | None], ...] = (
    ("급여이체", None),
    ("자동이체", None),
    ("신규고객", None),
    ("카드실적", None),
    ("마케팅동의", None),
    ("공과금이체", None),
    ("연금수령", None),
    ("비대면가입", None),
    ("공제가입", "신협공제 등 공제 상품 가입 실적 조건"),
    ("연령조건", "가입 연령 기준 충족 조건 (청년/어린이/시니어 등 나이 관련)"),
    ("주거래은행", "당행을 주거래 은행으로 지정하거나 복합 거래실적(급여·카드·자동이체 등 조합) 충족 조건"),
    ("기타", None),
)

CONDITION_TYPES: tuple[str, ...] = tuple(ct for ct, _ in CONDITION_TYPE_DEFINITIONS)
DEFAULT_CONDITION_TYPE: str = "기타"
