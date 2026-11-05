"""user_manual_entry 추가 - 캘린더에서 사용자가 직접 기록한 상품

FE 캘린더의 '상품 정보 기록하기'는 지금까지 브라우저 메모리에만 있어 새로고침하면 사라졌다.
추천·가입(user_holding)은 포트폴리오에 묶인 스냅샷이라 성격이 달라 별도 테이블로 둔다.

  - product_id : 상품 목록에서 골랐을 때만. 상품이 지워져도 기록은 남도록 SET NULL
  - product_name : 목록에서 골라도 이름을 같이 저장한다 (스냅샷)

Revision ID: c6d1e8f2a7b4
Revises: b8e3f1a6c4d2
Create Date: 2026-11-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql.elements import conv

from alembic import op

revision: str = "c6d1e8f2a7b4"
down_revision: str | Sequence[str] | None = "b8e3f1a6c4d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_manual_entry",
        sa.Column("entry_id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False, comment="사용자가 캘린더에서 고른 날짜"),
        sa.Column("institution_name", sa.String(length=100), nullable=False, comment="FE 기관 선택지 이름 그대로"),
        sa.Column(
            "product_id",
            sa.String(length=64),
            nullable=True,
            comment="상품 목록에서 골랐을 때만. 직접 입력했으면 NULL",
        ),
        sa.Column(
            "product_name",
            sa.String(length=200),
            nullable=False,
            comment="목록에서 골라도 이름을 같이 저장한다 (스냅샷)",
        ),
        sa.Column("amount", sa.BigInteger(), nullable=False, comment="금액(원)"),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount > 0", name=conv("ck_user_manual_entry_amount_positive")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.user_id"], name=conv("fk_user_manual_entry_user_id_app_user"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product.product_id"],
            name=conv("fk_user_manual_entry_product_id_product"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("entry_id", name=conv("pk_user_manual_entry")),
        comment="사용자가 캘린더에서 직접 기록한 상품. 추천·가입(user_holding)과 별개",
    )
    op.create_index("ix_user_manual_entry_user_id", "user_manual_entry", ["user_id", "entry_date"])


def downgrade() -> None:
    """테스트 전용. 운영 롤백 수단이 아니다 (README '마이그레이션 되돌리기' 참고). 기록은 사라진다."""
    op.drop_index("ix_user_manual_entry_user_id", table_name="user_manual_entry")
    op.drop_table("user_manual_entry")
