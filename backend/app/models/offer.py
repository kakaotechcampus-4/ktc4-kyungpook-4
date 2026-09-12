"""특판 후보와 검증 결과."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
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
from app.models.batch import BatchRun, CrawlHistory
from app.models.enums import (
    INSTITUTION_TYPES,
    OFFER_SOURCE_TYPES,
    PRODUCT_TYPES,
    RATE_TYPES,
    RESERVE_TYPES,
    VERIFICATION_STATUSES,
    one_of,
    one_of_or_null,
)

if TYPE_CHECKING:
    # product.py 가 이 파일을 import 하므로 런타임에 가져오면 순환이 된다.
    from app.models.product import Product


class SpecialOffer(Base):
    """커뮤니티/지역은행에서 발견한 특판 후보. 검증 전에는 사용자에게 노출하지 않는다."""

    __tablename__ = "special_offer"

    # 출처 URL + 상품명 해시 등으로 만든 애플리케이션 발급 ID
    offer_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="출처 URL + 상품명 해시 등으로 만든 애플리케이션 발급 ID",
    )
    run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("batch_run.run_id", ondelete="CASCADE"))
    crawl_history_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("crawl_history.id", ondelete="SET NULL"),
        comment="이 특판을 발견한 크롤링 건. 원문 추적용",
    )

    # --- 커뮤니티가 "주장"하는 값 (아직 신뢰하지 않는다) ---
    claimed_institution: Mapped[str] = mapped_column(
        String(100),
        comment="커뮤니티 글에 적힌 기관명 원문. 검증 단계에서 institution_alias 로 코드를 찾아 붙인다",
    )
    institution_type: Mapped[str | None] = mapped_column(String(20))
    product_type: Mapped[str | None] = mapped_column(String(20))
    claimed_product_name: Mapped[str | None] = mapped_column(String(200))
    claimed_base_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    claimed_max_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), comment="커뮤니티 글이 주장한 금리. 검증 전 값이라 노출 금지"
    )
    raw_html: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str | None] = mapped_column(String(20))
    source_url: Mapped[str | None] = mapped_column(String(1000))

    # --- 은행 사이트에서 확인한 값 ---
    # 기관 매칭에 성공한 뒤 채워진다. None 이면 아직 미해결.
    institution_code: Mapped[str | None] = mapped_column(
        String(20),
        ForeignKey("institution.institution_code"),
        comment="기관 매칭에 성공한 뒤 채워진다. NULL 이면 아직 미해결",
    )
    matched_product_name: Mapped[str | None] = mapped_column(String(200))
    verified_amount_cap: Mapped[int | None] = mapped_column(BigInteger)
    verified_terms_text: Mapped[str | None] = mapped_column(Text)
    verify_source_url: Mapped[str | None] = mapped_column(String(1000))

    verification_status: Mapped[str] = mapped_column(String(20), server_default=text("'PENDING'"))
    rejected_reason: Mapped[str | None] = mapped_column(String(200))
    verify_attempt_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    last_verify_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped[BatchRun] = relationship()
    crawl_history: Mapped[CrawlHistory | None] = relationship()
    options: Mapped[list["SpecialOfferOption"]] = relationship(
        back_populates="offer", cascade="all, delete-orphan", passive_deletes=True
    )
    product: Mapped["Product | None"] = relationship(back_populates="offer")

    __table_args__ = (
        CheckConstraint(one_of_or_null("institution_type", INSTITUTION_TYPES), name="institution_type"),
        CheckConstraint(one_of_or_null("product_type", PRODUCT_TYPES), name="product_type"),
        CheckConstraint(one_of_or_null("source_type", OFFER_SOURCE_TYPES), name="source_type"),
        CheckConstraint(one_of("verification_status", VERIFICATION_STATUSES), name="verification_status"),
        CheckConstraint(
            "(claimed_base_rate IS NULL OR claimed_base_rate >= 0)"
            " AND (claimed_max_rate IS NULL OR claimed_base_rate IS NULL"
            " OR claimed_max_rate >= claimed_base_rate)",
            name="rates",
        ),
        # 검증 통과했다면 근거(기관 코드·시각·출처)가 반드시 남아 있어야 한다.
        # 확인 금리는 SpecialOfferOption 에 있어 여기서 CHECK 로 막지 못한다 (승격 배치가 검사한다).
        CheckConstraint(
            "verification_status <> 'VERIFIED'"
            " OR (verified_at IS NOT NULL"
            " AND verify_source_url IS NOT NULL AND institution_code IS NOT NULL)",
            name="verified_evidence",
        ),
        CheckConstraint(
            "verification_status <> 'REJECTED' OR rejected_reason IS NOT NULL",
            name="rejected_reason",
        ),
        CheckConstraint("verify_attempt_count >= 0", name="verify_attempt_count"),
        Index(
            "ix_special_offer_verification_status",
            "verification_status",
            text("discovered_at DESC"),
        ),
        Index("ix_special_offer_run_id", "run_id"),
        {"comment": "커뮤니티/지역은행에서 발견한 특판 후보. 검증 전에는 사용자에게 노출하지 않는다"},
    )


class SpecialOfferOption(Base):
    """은행 사이트에서 확인한 특판의 기간별 금리.

    특판도 12/24개월 식으로 여러 기간을 준다. 승격 시 ProductOption 으로 1:1 옮겨간다.
    """

    __tablename__ = "special_offer_option"

    offer_option_id: Mapped[str] = mapped_column(
        String(96),
        primary_key=True,
        comment="offer_id + 기간 + 이자방식 조합. 승격 시 product_option 으로 1:1 옮겨간다",
    )
    offer_id: Mapped[str] = mapped_column(String(64), ForeignKey("special_offer.offer_id", ondelete="CASCADE"))
    period_months: Mapped[int] = mapped_column(Integer)
    rate_type: Mapped[str] = mapped_column(String(10), server_default=text("'단리'"))
    reserve_type: Mapped[str] = mapped_column(String(20), server_default=text("'해당없음'"))
    base_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    max_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))

    offer: Mapped[SpecialOffer] = relationship(back_populates="options")

    __table_args__ = (
        UniqueConstraint("offer_id", "period_months", "rate_type", "reserve_type"),
        CheckConstraint("period_months > 0", name="period_months"),
        CheckConstraint(one_of("rate_type", RATE_TYPES), name="rate_type"),
        CheckConstraint(one_of("reserve_type", RESERVE_TYPES), name="reserve_type"),
        CheckConstraint("base_rate >= 0 AND max_rate >= base_rate", name="rates"),
        Index("ix_special_offer_option_offer_id", "offer_id"),
        {"comment": "은행 사이트에서 확인한 특판의 기간별 금리. 특판도 12/24개월 식으로 여러 기간을 줄 수 있다"},
    )
