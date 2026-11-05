"""user_portfolio += closed_at - 새 안을 확정하면 이전 안을 그만둔 시각

로드맵의 '총 이자'는 그만둔 안의 이자도 그만둔 시각까지는 센다. 지금까지는 다시 확정해도
이전 안이 진행중으로 남아 이자가 겹쳐 셌다.

  - closed_at : 다른 안을 새로 확정해 그만둔 시각. 진행중이면 NULL
  - ck_user_portfolio_closed : closed_at 이 있으면 status 는 '완료'

기존 행은 모두 NULL 로 남는다 (지금까지 그만둔 기록이 없다).

Revision ID: d2f7a9c3e1b5
Revises: c6d1e8f2a7b4
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql.elements import conv

from alembic import op

revision: str = "d2f7a9c3e1b5"
down_revision: str | Sequence[str] | None = "c6d1e8f2a7b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_portfolio",
        sa.Column(
            "closed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="다른 안을 새로 확정해 그만둔 시각. 진행중이면 NULL",
        ),
    )
    op.create_check_constraint(conv("ck_user_portfolio_closed"), "user_portfolio", "closed_at IS NULL OR status = '완료'")


def downgrade() -> None:
    """테스트 전용. 운영 롤백 수단이 아니다 (README '마이그레이션 되돌리기' 참고). 그만둔 시각은 사라진다."""
    op.drop_constraint(conv("ck_user_portfolio_closed"), "user_portfolio", type_="check")
    op.drop_column("user_portfolio", "closed_at")
