"""product.join_channel 제거 - 가입 채널은 product_option 에만 둔다

채널이 product 와 product_option 두 군데에 있으면 둘이 모순돼도 DB 가 막지 못한다.
(product.join_channel = '영업점' 인데 그 상품의 옵션 하나가 '비대면' 인 행이 들어갈 수 있다.)
금리가 채널마다 갈리므로 원본은 옵션 쪽이어야 하고, 상품 단위 채널은 옵션에서 계산할 수
있으니 product 쪽을 지운다. 임포터도 이미 옵션 채널을 모아서 이 값을 만들고 있었다.

Revision ID: c3d8f2a61b07
Revises: b1c4e7a90f32
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql.elements import conv

from alembic import op

revision: str = "c3d8f2a61b07"
down_revision: str | Sequence[str] | None = "b1c4e7a90f32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(conv("ck_product_join_channel"), "product", type_="check")
    op.drop_column("product", "join_channel")


def downgrade() -> None:
    """테스트 전용. 운영 롤백 수단이 아니다 (README '마이그레이션 되돌리기' 참고).

    지운 값은 옵션에서 다시 계산할 수 있어 이 downgrade 는 데이터를 잃지 않는다.
    임포터가 쓰던 규칙 그대로 - 옵션 채널이 하나면 그 값, 여러 개면 '전체', 옵션이 없으면 NULL.
    """
    op.add_column("product", sa.Column("join_channel", sa.String(length=20), nullable=True))
    op.execute("""
        UPDATE product p
        SET join_channel = CASE WHEN c.n = 1 THEN c.one ELSE '전체' END
        FROM (
            SELECT product_id, count(DISTINCT join_channel) AS n, min(join_channel) AS one
            FROM product_option
            GROUP BY product_id
        ) c
        WHERE c.product_id = p.product_id
    """)
    op.create_check_constraint(
        conv("ck_product_join_channel"),
        "product",
        "join_channel IS NULL OR join_channel IN ('비대면', '영업점', '전체')",
    )
