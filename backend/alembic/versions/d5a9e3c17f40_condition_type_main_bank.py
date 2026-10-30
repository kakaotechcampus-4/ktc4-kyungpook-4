"""condition_type += 주거래은행

AI 파트가 우대조건 분류에 '주거래은행'을 추가했다 (ai/src/schemas/condition_types.py).
당행을 주거래 은행으로 지정하거나 급여·카드·자동이체 같은 복합 거래실적을 요구하는 조건이다.
지금까지는 '기타'로 분류되던 것들이다.

CHECK 에 없으면 주간 파이프라인이 이 값을 내보낸 뒤 임포트가 INSERT 단계에서 거부된다.

Revision ID: d5a9e3c17f40
Revises: c3d8f2a61b07
Create Date: 2026-10-11
"""

from collections.abc import Sequence

from sqlalchemy.sql.elements import conv

from alembic import op

revision: str = "d5a9e3c17f40"
down_revision: str | Sequence[str] | None = "c3d8f2a61b07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONDITION_TYPES_OLD = (
    "'급여이체', '자동이체', '신규고객', '카드실적', '마케팅동의', '공과금이체', '연금수령',"
    " '비대면가입', '공제가입', '연령조건', '기타'"
)
CONDITION_TYPES = (
    "'급여이체', '자동이체', '신규고객', '카드실적', '마케팅동의', '공과금이체', '연금수령',"
    " '비대면가입', '공제가입', '연령조건', '주거래은행', '기타'"
)
TABLES = ("product_condition", "user_profile_extra")


def _swap_check(table: str, body: str) -> None:
    """CHECK 은 ALTER 가 없다. 같은 이름으로 지웠다 다시 만든다 (b1c4e7a90f32 와 같은 방식)."""
    op.drop_constraint(conv(f"ck_{table}_condition_type"), table, type_="check")
    op.create_check_constraint("condition_type", table, f"condition_type IN ({body})")


def upgrade() -> None:
    for table in TABLES:
        _swap_check(table, CONDITION_TYPES)


def downgrade() -> None:
    """테스트 전용. 운영 롤백 수단이 아니다 (README '마이그레이션 되돌리기' 참고).

    좁힌 어휘에 걸리는 행은 지운다. 지운 행은 돌아오지 않는다.
    """
    for table in TABLES:
        op.execute(f"DELETE FROM {table} WHERE condition_type = '주거래은행'")
        _swap_check(table, CONDITION_TYPES_OLD)
