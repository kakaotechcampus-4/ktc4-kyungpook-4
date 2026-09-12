"""사용자가 선택한 배분안과 그 구성 상품."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    HOLDING_STATUSES,
    PORTFOLIO_STATUSES,
    PORTFOLIO_TYPES,
    one_of,
)
from app.models.product import ProductCondition, ProductOption
from app.models.profile import UserProfile
from app.models.user import AppUser


class UserPortfolio(Base):
    """제안만 하고 사용자가 안 고른 안은 저장하지 않는다."""

    __tablename__ = "user_portfolio"

    portfolio_id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.user_id", ondelete="CASCADE"))
    # 계산 근거가 된 조회 건은 지워지면 안 된다 (RESTRICT)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user_profile.profile_id", ondelete="RESTRICT"))
    portfolio_type: Mapped[str] = mapped_column(String(10))
    goal_amount: Mapped[int | None] = mapped_column(BigInteger)
    goal_date: Mapped[date | None] = mapped_column(Date)
    # 만기 시 예상 세후 수령액(원)
    after_tax_total: Mapped[int | None] = mapped_column(BigInteger, comment="만기 시 예상 세후 수령액(원)")
    status: Mapped[str] = mapped_column(String(10), server_default=text("'진행중'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[AppUser] = relationship()
    profile: Mapped[UserProfile] = relationship()
    holdings: Mapped[list["UserHolding"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint(one_of("portfolio_type", PORTFOLIO_TYPES), name="portfolio_type"),
        CheckConstraint(one_of("status", PORTFOLIO_STATUSES), name="status"),
        CheckConstraint(
            "(goal_amount IS NULL OR goal_amount > 0) AND (after_tax_total IS NULL OR after_tax_total >= 0)",
            name="amounts",
        ),
        Index("ix_user_portfolio_user_id", "user_id", text("created_at DESC")),
        Index("ix_user_portfolio_profile_id", "profile_id"),
        {"comment": "사용자가 실제로 선택한 배분안. 제안만 하고 안 고른 안은 저장하지 않는다"},
    )


class UserHolding(Base):
    """배분안을 이루는 가입 상품 1건."""

    __tablename__ = "user_holding"

    holding_id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user_portfolio.portfolio_id", ondelete="CASCADE"))
    # 가입한 기간옵션. 상품이 아니라 옵션을 가리켜야 "어느 기간으로 가입했는지"가 남는다.
    # 원본이 공시에서 사라져도 아래 스냅샷 컬럼으로 보유 이력은 살아남는다.
    option_id: Mapped[str | None] = mapped_column(
        String(96),
        ForeignKey("product_option.option_id", ondelete="SET NULL"),
        comment='가입한 기간옵션. 상품이 아니라 옵션을 가리켜야 "어느 기간으로 가입했는지"가 남는다',
    )
    institution: Mapped[str] = mapped_column(
        String(100), comment="가입 시점 기관명 스냅샷. 원본이 사라져도 보여줘야 한다"
    )
    product_name: Mapped[str] = mapped_column(String(200))
    amount: Mapped[int | None] = mapped_column(BigInteger)
    monthly_amount: Mapped[int | None] = mapped_column(BigInteger)
    base_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), comment="가입 시점 기본금리 스냅샷. 우대 가산 전")
    effective_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        comment="우대조건까지 반영해 확정된 가입 시점 금리. 적용 내역은 user_holding_condition 에 있다",
    )
    max_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        comment='가입 시점 상품 최고금리 스냅샷. "광고 7.5% 중 당신은 5.5%" 를 보여주기 위한 값',
    )
    start_date: Mapped[date] = mapped_column(Date)
    maturity_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), server_default=text("'유지중'"))

    portfolio: Mapped[UserPortfolio] = relationship(back_populates="holdings")
    option: Mapped[ProductOption | None] = relationship()
    applied_conditions: Mapped[list["UserHoldingCondition"]] = relationship(
        back_populates="holding", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint(one_of("status", HOLDING_STATUSES), name="status"),
        # 예금이면 amount, 적금이면 monthly_amount. 둘 다 비면 금액 없는 보유가 된다.
        CheckConstraint("amount IS NOT NULL OR monthly_amount IS NOT NULL", name="amount"),
        CheckConstraint(
            "(amount IS NULL OR amount > 0) AND (monthly_amount IS NULL OR monthly_amount > 0)",
            name="amount_positive",
        ),
        # 기본금리 <= 내 확정금리 <= 상품 최고금리. 계산 결과가 이 범위를 벗어나면 버그다.
        CheckConstraint(
            "base_rate >= 0 AND base_rate <= effective_rate AND effective_rate <= max_rate",
            name="rates",
        ),
        CheckConstraint("maturity_date IS NULL OR maturity_date >= start_date", name="maturity_date"),
        Index("ix_user_holding_portfolio_id", "portfolio_id"),
        Index(
            "ix_user_holding_maturity_date",
            "maturity_date",
            postgresql_where=text("status = '유지중'"),
        ),
        {"comment": "배분안을 이루는 가입 상품 1건"},
    )


class UserHoldingCondition(Base):
    """이 보유 건의 확정금리가 어떻게 나왔는지에 대한 근거.

    사용자가 "왜 5.5% 인가요?" 라고 물으면 이걸 그대로 보여준다.
    원본 ProductCondition 은 배치가 덮어쓰면서 사라질 수 있으므로 세 컬럼을 복사해 둔다.
    """

    __tablename__ = "user_holding_condition"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    holding_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user_holding.holding_id", ondelete="CASCADE"))
    condition_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("product_condition.condition_id", ondelete="SET NULL"),
        comment="원본 우대조건. 상품이 덮어써지면 NULL 이 되지만 아래 스냅샷은 남는다",
    )
    condition_type: Mapped[str] = mapped_column(String(50))
    rate_bonus: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        comment="가입 시점에 실제로 가산된 %p. 전부 더하면 effective_rate - base_rate 가 된다",
    )
    evidence_text: Mapped[str | None] = mapped_column(Text, comment="가산 근거가 된 약관 원문 인용 스냅샷")

    holding: Mapped[UserHolding] = relationship(back_populates="applied_conditions")
    condition: Mapped[ProductCondition | None] = relationship()

    __table_args__ = (
        # 같은 종류의 조건이 한 보유 건에 두 번 적용되는 일은 없다 (계단 조건도 택1)
        UniqueConstraint("holding_id", "condition_type"),
        CheckConstraint("rate_bonus >= 0", name="rate_bonus"),
        Index("ix_user_holding_condition_holding_id", "holding_id"),
        {
            "comment": "이 보유 건의 확정금리가 어떻게 나왔는지에 대한 근거."
            ' 사용자가 "왜 5.5%?" 라고 물으면 이걸 보여준다'
        },
    )
