"""상품 / 기간옵션 / 우대조건.

상품 정보는 덮어쓰기다(이력을 쌓지 않는다).
단 DELETE + INSERT 로 갱신하면 UserHolding 이 물고 있는 링크가 매 배치마다 끊긴다.
PK 가 전부 결정적으로 생성되는 문자열이므로 반드시 upsert (ON CONFLICT DO UPDATE) 로 갱신한다.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.batch import BatchRun
from app.models.enums import (
    CONDITION_VERIFY_STATUSES,
    CONFIDENCE_BADGES,
    JOIN_CHANNELS,
    PARSE_STATUSES,
    PRODUCT_SOURCES,
    PRODUCT_TYPES,
    RATE_TYPES,
    RESERVE_TYPES,
    THRESHOLD_UNITS,
    one_of,
    one_of_or_null,
)
from app.models.offer import SpecialOffer


class Product(Base):
    """상품 기본정보. 금리는 기간마다 달라서 ProductOption 이 들고 있다."""

    __tablename__ = "product"

    # 공시 = 금융회사코드 + 상품코드 조합, 특판 = "SP-" + offer_id.
    # 배치 간 안정적이어야 한다.
    product_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="공시 = 금융회사코드 + 상품코드 조합, 특판 = 'SP-' || offer_id. 배치 간 안정적이어야 한다",
    )
    offer_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("special_offer.offer_id", ondelete="SET NULL"))
    # 배치 기록을 정리해도 상품은 남아야 한다 (전에는 CASCADE 라 통째로 삭제됐다)
    run_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("batch_run.run_id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String(10))
    institution_code: Mapped[str] = mapped_column(String(20), ForeignKey("institution.institution_code"))
    product_name: Mapped[str] = mapped_column(String(200))
    product_type: Mapped[str] = mapped_column(String(20))
    amount_min: Mapped[int | None] = mapped_column(BigInteger, comment="최소 가입금액(예금) / 최소 총 납입액(적금)")
    amount_cap: Mapped[int | None] = mapped_column(BigInteger, comment="최대 가입금액(예금) / 최대 총 납입액(적금)")
    monthly_min: Mapped[int | None] = mapped_column(BigInteger, comment="적금 월 최소 납입액. 예금은 NULL")
    # 총 한도와 별개다. 이걸 모르면 월 배분액이 한도를 넘는 배분안이 나온다.
    monthly_cap: Mapped[int | None] = mapped_column(
        BigInteger,
        comment="적금 월 최대 납입액. 총 한도와 별개다 - 이걸 모르면 월 배분액이 한도를 넘는 배분안이 나온다",
    )
    # 우대조건 파싱(LLM)의 입력 원문
    terms_text: Mapped[str | None] = mapped_column(Text, comment="우대조건 파싱(LLM)의 입력 원문")
    region: Mapped[str | None] = mapped_column(String(50))
    join_channel: Mapped[str | None] = mapped_column(String(20))
    # --- 가입 "자격". 못 채우면 금리가 낮은 게 아니라 아예 가입이 안 된다 ---
    membership_required: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        comment="조합원 가입(출자금)이 있어야 가입 가능. 신협·새마을금고 예탁금. 우대조건이 아니라 자격이다",
    )
    new_customer_only: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), comment="해당 기관 신규 고객 전용"
    )
    min_age: Mapped[int | None] = mapped_column(Integer, comment="가입 가능 최소 만 나이. 청년 전용 상품 등")
    max_age: Mapped[int | None] = mapped_column(Integer, comment="가입 가능 최대 만 나이")
    parse_status: Mapped[str] = mapped_column(String(10), server_default=text("'PENDING'"))
    # 이 상품 정보가 유효한 기준일. 지난 날짜면 재조회 대상.
    snapshot_date: Mapped[date] = mapped_column(
        Date,
        server_default=func.current_date(),
        comment="이 상품 정보가 유효한 기준일. 지난 날짜면 재조회 대상",
    )
    sale_end_date: Mapped[date | None] = mapped_column(
        Date,
        comment="판매 종료 예정일. 특판은 채워지고 공시 상품은 대개 NULL - "
        "그쪽은 snapshot_date 가 오래되면 사라진 것으로 본다",
    )
    # 행을 지우면 가입자의 금리 근거가 끊긴다. 삭제 대신 이 값을 내린다.
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        comment="추천 후보에서 뺄 때 쓴다. 행을 지우면 가입자의 금리 근거가 끊기므로 삭제 대신 이 값을 내린다",
    )

    offer: Mapped[SpecialOffer | None] = relationship(back_populates="product")
    run: Mapped[BatchRun | None] = relationship()
    options: Mapped[list["ProductOption"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", passive_deletes=True
    )
    conditions: Mapped[list["ProductCondition"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        # 특판 1건은 상품 1건으로만 승격된다
        UniqueConstraint("offer_id"),
        CheckConstraint(one_of("source", PRODUCT_SOURCES), name="source"),
        # OFFICIAL 은 금감원 공시, SPECIAL 은 반드시 원본 특판을 갖는다
        CheckConstraint(
            "(source = 'SPECIAL' AND offer_id IS NOT NULL) OR (source = 'OFFICIAL' AND offer_id IS NULL)",
            name="source_offer",
        ),
        CheckConstraint(one_of("product_type", PRODUCT_TYPES), name="product_type"),
        CheckConstraint(one_of_or_null("join_channel", JOIN_CHANNELS), name="join_channel"),
        CheckConstraint(one_of("parse_status", PARSE_STATUSES), name="parse_status"),
        CheckConstraint(
            "(amount_min IS NULL OR amount_min > 0)"
            " AND (amount_cap IS NULL OR amount_cap > 0)"
            " AND (monthly_min IS NULL OR monthly_min > 0)"
            " AND (monthly_cap IS NULL OR monthly_cap > 0)"
            " AND (amount_min IS NULL OR amount_cap IS NULL OR amount_min <= amount_cap)"
            " AND (monthly_min IS NULL OR monthly_cap IS NULL OR monthly_min <= monthly_cap)",
            name="amounts",
        ),
        # 월 납입 한도는 적금에만 있다. 예금·예탁금은 목돈을 한 번에 넣는다.
        CheckConstraint(
            "product_type = '적금' OR (monthly_min IS NULL AND monthly_cap IS NULL)",
            name="monthly_only_savings",
        ),
        CheckConstraint(
            "(min_age IS NULL OR min_age >= 0)"
            " AND (max_age IS NULL OR max_age >= 0)"
            " AND (min_age IS NULL OR max_age IS NULL OR min_age <= max_age)",
            name="age",
        ),
        Index(
            "ix_product_product_type",
            "product_type",
            postgresql_where=text("parse_status = 'PARSED' AND is_active"),
        ),
        Index("ix_product_institution_code", "institution_code"),
        Index("ix_product_snapshot_date", "snapshot_date"),
        Index("ix_product_run_id", "run_id"),
        {"comment": "상품 기본정보(금감원 baseList 에 대응). 금리는 기간마다 달라서 product_option 이 들고 있다"},
    )


class ProductOption(Base):
    """저축기간별 금리. 추천·포트폴리오가 실제로 고르는 단위."""

    __tablename__ = "product_option"

    # product_id + 기간 + 이자방식 조합으로 결정적으로 생성.
    # 배치가 upsert 해도 UserHolding 링크가 유지된다.
    option_id: Mapped[str] = mapped_column(
        String(96),
        primary_key=True,
        comment="product_id + 기간 + 이자방식 조합으로 결정적으로 생성."
        " 배치가 upsert 해도 user_holding 링크가 유지된다",
    )
    product_id: Mapped[str] = mapped_column(String(64), ForeignKey("product.product_id", ondelete="CASCADE"))
    period_months: Mapped[int] = mapped_column(Integer)
    rate_type: Mapped[str] = mapped_column(String(10), server_default=text("'단리'"))
    # 적금의 적립 방식. 예금은 '해당없음'.
    # NULL 을 쓰면 UNIQUE 가 중복을 못 막아서 기본값을 둔다.
    reserve_type: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'해당없음'"),
        comment="적금의 적립 방식. 예금은 '해당없음'. NULL 을 쓰면 UNIQUE 가 중복을 못 막아서 기본값을 둔다",
    )
    base_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    max_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))

    product: Mapped[Product] = relationship(back_populates="options")

    __table_args__ = (
        # 같은 상품에 (기간, 이자방식, 적립방식) 이 겹치는 옵션은 없다
        UniqueConstraint("product_id", "period_months", "rate_type", "reserve_type"),
        CheckConstraint("period_months > 0", name="period_months"),
        CheckConstraint(one_of("rate_type", RATE_TYPES), name="rate_type"),
        CheckConstraint(one_of("reserve_type", RESERVE_TYPES), name="reserve_type"),
        CheckConstraint("base_rate >= 0 AND max_rate >= base_rate", name="rates"),
        Index("ix_product_option_product_id", "product_id"),
        Index("ix_product_option_period_months", "period_months", text("max_rate DESC")),
        {"comment": "저축기간별 금리(금감원 optionList 에 대응). 추천·포트폴리오가 실제로 고르는 단위"},
    )


class ProductCondition(Base):
    """약관에서 뽑아낸 우대조건 1개.

    기간 제한은 applies_period_* 로 표현하므로 옵션이 아니라 상품 단위로 붙인다.
    """

    __tablename__ = "product_condition"

    condition_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), ForeignKey("product.product_id", ondelete="CASCADE"))
    # 닫힌 어휘 목록 확정 필요.
    # UserProfileExtra.condition_type 과 같은 값을 써야 매칭이 된다.
    condition_type: Mapped[str] = mapped_column(
        String(50),
        comment="닫힌 어휘 목록 확정 필요. user_profile_extra.condition_type 과 같은 값을 써야 매칭이 된다",
    )
    rate_bonus: Mapped[Decimal] = mapped_column(Numeric(4, 2), server_default=text("0"))
    threshold_value: Mapped[int | None] = mapped_column(BigInteger)
    threshold_unit: Mapped[str | None] = mapped_column(String(10))
    applies_period_min: Mapped[int | None] = mapped_column(Integer)
    applies_period_max: Mapped[int | None] = mapped_column(Integer)
    # 같은 그룹의 조건은 하나만 적용된다 (택1 우대)
    exclusive_group: Mapped[str | None] = mapped_column(
        String(50), comment="같은 그룹의 조건은 하나만 적용된다 (택1 우대)"
    )
    # 가산 근거가 된 약관 원문 인용. 사용자에게 그대로 보여준다.
    evidence_text: Mapped[str | None] = mapped_column(
        Text, comment="가산 근거가 된 약관 원문 인용. 사용자에게 그대로 보여준다"
    )
    evidence_url: Mapped[str | None] = mapped_column(String(1000))
    # 파싱 결과와 약관 대조 결과. EXCESS = 약관에 없는 조건을 만들어냄.
    verification_status: Mapped[str | None] = mapped_column(
        String(10), comment="파싱 결과와 약관 대조 결과. EXCESS = 약관에 없는 조건을 만들어냄"
    )
    confidence_badge: Mapped[str] = mapped_column(String(10), server_default=text("'검수대기'"))

    product: Mapped[Product] = relationship(back_populates="conditions")

    __table_args__ = (
        CheckConstraint(one_of_or_null("threshold_unit", THRESHOLD_UNITS), name="threshold_unit"),
        # 임계값과 단위는 항상 짝으로 채워진다
        CheckConstraint("(threshold_value IS NULL) = (threshold_unit IS NULL)", name="threshold_pair"),
        CheckConstraint(
            "applies_period_min IS NULL OR applies_period_max IS NULL OR applies_period_min <= applies_period_max",
            name="applies_period",
        ),
        CheckConstraint("rate_bonus >= 0", name="rate_bonus"),
        CheckConstraint(
            one_of_or_null("verification_status", CONDITION_VERIFY_STATUSES),
            name="verification_status",
        ),
        CheckConstraint(one_of("confidence_badge", CONFIDENCE_BADGES), name="confidence_badge"),
        Index("ix_product_condition_product_id", "product_id"),
        {"comment": "약관에서 뽑아낸 우대조건 1개. 기간 제한은 applies_period_* 로 표현하므로 상품 단위로 붙인다"},
    )
