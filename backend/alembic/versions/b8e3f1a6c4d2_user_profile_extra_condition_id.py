"""user_profile_extra += condition_id / raw_answer, (profile_id, condition_id) 중복 금지 - 챗봇 '기타' 조건 답변 저장

챗봇은 추천 결과에 들어간 상품의 '기타' 우대조건만 묻는다. '기타' 는 상품마다 내용이 달라
condition_type 만으로는 어느 조건의 답인지 구분이 안 되므로 condition_id 를 함께 저장한다.

  - condition_id : product_condition.condition_id. FK 없음 (ERD 재임포트로 바뀌거나 사라질 수 있다)
  - raw_answer   : 사용자가 입력한 원문. answer_value 는 이것을 해석한 결과(true/false)
  - (profile_id, condition_id) 중복 금지 : 조회 1건에서 같은 조건의 답은 하나만 둔다

condition_id 는 NOT NULL 이다. 이 테이블은 지금까지 쓰는 코드가 없어 비어 있으므로 바로 추가할 수 있다.

Revision ID: b8e3f1a6c4d2
Revises: a4c7e1f05d22
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql.elements import conv

from alembic import op

revision: str = "b8e3f1a6c4d2"
down_revision: str | Sequence[str] | None = "a4c7e1f05d22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_profile_extra",
        sa.Column(
            "condition_id",
            sa.String(length=64),
            nullable=False,
            comment="챗봇이 물어본 우대조건 product_condition.condition_id. FK 없음 - ERD 재임포트로 바뀔 수 있다",
        ),
    )
    op.add_column(
        "user_profile_extra",
        sa.Column(
            "raw_answer",
            sa.Text(),
            nullable=True,
            comment="사용자가 입력한 원문 답변. answer_value 는 이것을 해석한 결과(true/false)",
        ),
    )
    op.create_unique_constraint(
        conv("uq_user_profile_extra_profile_id"), "user_profile_extra", ["profile_id", "condition_id"]
    )


def downgrade() -> None:
    """테스트 전용. 운영 롤백 수단이 아니다 (README '마이그레이션 되돌리기' 참고). 두 컬럼의 값은 사라진다."""
    op.drop_constraint(conv("uq_user_profile_extra_profile_id"), "user_profile_extra", type_="unique")
    op.drop_column("user_profile_extra", "raw_answer")
    op.drop_column("user_profile_extra", "condition_id")
