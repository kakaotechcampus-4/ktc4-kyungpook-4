"""portfolio_type += 안정형

2026-10-13 포트폴리오 기준 개편으로 1금융(은행) 상품만으로 구성한 '안정형'이 생겼다.
단일형은 비교 기준선이라 가입(저장) 대상이 아니므로 넣지 않는다.

Revision ID: f3a1d6b29c58
Revises: e7b2c4d8a913
Create Date: 2026-10-13
"""

from collections.abc import Sequence

from sqlalchemy.sql.elements import conv

from alembic import op

revision: str = "f3a1d6b29c58"
down_revision: str | Sequence[str] | None = "e7b2c4d8a913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TYPES_OLD = "'단순형', '균형형', '최대형'"
TYPES = "'단순형', '균형형', '최대형', '안정형'"


def _swap_check(body: str) -> None:
    op.drop_constraint(conv("ck_user_portfolio_portfolio_type"), "user_portfolio", type_="check")
    op.create_check_constraint("portfolio_type", "user_portfolio", f"portfolio_type IN ({body})")


def upgrade() -> None:
    _swap_check(TYPES)


def downgrade() -> None:
    """테스트 전용. 운영 롤백 수단이 아니다 (README '마이그레이션 되돌리기' 참고). 안정형 포트폴리오는 지운다."""
    op.execute("DELETE FROM user_portfolio WHERE portfolio_type = '안정형'")
    _swap_check(TYPES_OLD)
