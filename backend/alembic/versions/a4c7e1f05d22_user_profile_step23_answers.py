"""user_profile += STEP2·3 답변 컬럼 / user_profile_tax_exempt.category CHECK

앱 STEP2 에 새로 생긴 질문 3개(적금 자동이체·연금계좌 이전·공제 가입)를 받을 컬럼과,
답변 원문을 그대로 남겨 두는 answers(jsonb)를 추가한다.
비과세종합저축 대상 항목은 값 집합이 정해졌으므로 CHECK 를 건다 (enums.TAX_EXEMPT_CATEGORIES).

Revision ID: a4c7e1f05d22
Revises: f3a1d6b29c58
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import conv

from alembic import op

revision: str = "a4c7e1f05d22"
down_revision: str | Sequence[str] | None = "f3a1d6b29c58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TAX_EXEMPT_CATEGORY = "category IN ('65세이상', '장애인', '유공자', '기초생활수급자')"


def upgrade() -> None:
    op.add_column(
        "user_profile",
        sa.Column(
            "savings_auto_transfer",
            sa.Boolean(),
            nullable=True,
            comment="적금 납입을 자동이체로 걸 수 있음. NULL = 모름",
        ),
    )
    op.add_column(
        "user_profile",
        sa.Column(
            "pension_transfer",
            sa.Boolean(),
            nullable=True,
            comment="연금 수령 계좌를 옮길 수 있음. 연금수령 우대조건 판정용. NULL = 모름",
        ),
    )
    op.add_column(
        "user_profile",
        sa.Column(
            "coop_insurance",
            sa.Boolean(),
            nullable=True,
            comment="공제(새마을금고·신협 등) 가입 실적이 있거나 가입 의사가 있음. 공제가입 우대조건 판정용. NULL = 모름",
        ),
    )
    op.add_column(
        "user_profile",
        sa.Column(
            "answers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="STEP2·3 원문 답변(앱 선택지 문구 그대로). 해석 규칙이 바뀌어도 다시 계산할 수 있게 보관",
        ),
    )
    op.create_check_constraint("category", "user_profile_tax_exempt", TAX_EXEMPT_CATEGORY)


def downgrade() -> None:
    """테스트 전용. 운영 롤백 수단이 아니다 (README '마이그레이션 되돌리기' 참고). 네 컬럼의 값은 사라진다."""
    op.drop_constraint(conv("ck_user_profile_tax_exempt_category"), "user_profile_tax_exempt", type_="check")
    op.drop_column("user_profile", "answers")
    op.drop_column("user_profile", "coop_insurance")
    op.drop_column("user_profile", "pension_transfer")
    op.drop_column("user_profile", "savings_auto_transfer")
