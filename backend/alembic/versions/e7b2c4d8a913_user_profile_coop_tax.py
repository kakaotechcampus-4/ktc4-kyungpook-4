"""user_profile += coop_tax_eligible / coop_exempt_used - 조합 예탁금 감면 세율 판정

신협·새마을금고 예탁금은 1인당 3천만원까지 소득세가 감면되는데, 2026년 가입분부터 총급여
7천만원 초과 여부로 세율이 갈린다 (조세특례제한법 제89조의3, 2025-12 개정).
그 판정에 필요한 두 값을 받는다. 계산은 app/services/tax.py.

  - coop_tax_eligible : 총급여 7천만원 이하 여부. NULL = 모름
  - coop_exempt_used  : 다른 조합에 이미 감면으로 넣어 둔 예탁금(원). NULL = 모름

tax_exempt_used 는 그대로 둔다. 비과세종합저축 한도용이라 조합 예탁금 한도와 별개다.

Revision ID: e7b2c4d8a913
Revises: d5a9e3c17f40
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql.elements import conv

from alembic import op

revision: str = "e7b2c4d8a913"
down_revision: str | Sequence[str] | None = "d5a9e3c17f40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AMOUNTS_OLD = (
    "capital >= 0 AND monthly_saving >= 0 AND tax_exempt_used >= 0"
    " AND (monthly_card_usage IS NULL OR monthly_card_usage >= 0)"
)
AMOUNTS = AMOUNTS_OLD + " AND (coop_exempt_used IS NULL OR coop_exempt_used >= 0)"


def upgrade() -> None:
    op.add_column(
        "user_profile",
        sa.Column(
            "coop_tax_eligible",
            sa.Boolean(),
            nullable=True,
            comment="총급여 7천만원(종합소득 6천만원) 이하 여부. 조합 예탁금 감면 세율이 갈린다. NULL = 모름(초과로 계산)",
        ),
    )
    op.add_column(
        "user_profile",
        sa.Column(
            "coop_exempt_used",
            sa.BigInteger(),
            nullable=True,
            comment="다른 조합에 이미 감면으로 넣어 둔 예탁금(원). 1인당 3천만원 한도에서 뺀다. NULL = 모름(0 으로 계산)",
        ),
    )
    op.drop_constraint(conv("ck_user_profile_amounts"), "user_profile", type_="check")
    op.create_check_constraint("amounts", "user_profile", AMOUNTS)


def downgrade() -> None:
    """테스트 전용. 운영 롤백 수단이 아니다 (README '마이그레이션 되돌리기' 참고). 두 컬럼의 값은 사라진다."""
    op.drop_constraint(conv("ck_user_profile_amounts"), "user_profile", type_="check")
    op.create_check_constraint("amounts", "user_profile", AMOUNTS_OLD)
    op.drop_column("user_profile", "coop_exempt_used")
    op.drop_column("user_profile", "coop_tax_eligible")
