"""사용자가 캘린더에서 직접 기록한 상품."""

from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Identity, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserManualEntry(Base):
    """추천·가입(user_holding)과 별개로, 사용자가 이미 가진 상품을 손으로 적어 둔 기록."""

    __tablename__ = "user_manual_entry"

    entry_id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.user_id", ondelete="CASCADE"))
    entry_date: Mapped[date] = mapped_column(Date, comment="사용자가 캘린더에서 고른 날짜")
    institution_name: Mapped[str] = mapped_column(String(100), comment="FE 기관 선택지 이름 그대로")
    # 상품이 재임포트로 지워져도 기록은 남아야 하므로 SET NULL. 이름은 product_name 에 따로 남는다
    product_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("product.product_id", ondelete="SET NULL"),
        comment="상품 목록에서 골랐을 때만. 직접 입력했으면 NULL",
    )
    product_name: Mapped[str] = mapped_column(String(200), comment="목록에서 골라도 이름을 같이 저장한다 (스냅샷)")
    amount: Mapped[int] = mapped_column(BigInteger, comment="금액(원)")
    memo: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_user_manual_entry_user_id", "user_id", "entry_date"),
        {"comment": "사용자가 캘린더에서 직접 기록한 상품. 추천·가입(user_holding)과 별개"},
    )
