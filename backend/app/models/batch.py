"""배치 실행과 크롤링 이력."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import BATCH_STATUSES, BATCH_TYPES, one_of


class BatchRun(Base):
    """배치 실행 1회. 수집된 모든 행이 이 run_id 를 들고 다녀 추적 단위가 된다."""

    __tablename__ = "batch_run"

    run_id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    batch_type: Mapped[str] = mapped_column(
        String(20),
        comment="MATURITY = 만기일 지난 user_holding 을 만기 처리하는 일배치. 사용자 접속과 무관하게 돌아야 한다",
    )
    # RUNNING 은 시작 시점에 행을 먼저 넣기 위해 둔 값
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'RUNNING'"),
        comment="RUNNING 은 시작 시점에 행을 먼저 넣기 위해 추가한 값",
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    failed_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    error_message: Mapped[str | None] = mapped_column(Text)

    crawl_histories: Mapped[list["CrawlHistory"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint(one_of("batch_type", BATCH_TYPES), name="batch_type"),
        CheckConstraint(one_of("status", BATCH_STATUSES), name="status"),
        CheckConstraint("processed_count >= 0 AND failed_count >= 0", name="counts"),
        CheckConstraint("finished_at IS NULL OR finished_at >= started_at", name="finished_at"),
        # 종료 상태인데 finished_at 이 비어 있으면 모니터링이 깨진다
        CheckConstraint("status = 'RUNNING' OR finished_at IS NOT NULL", name="terminal"),
        Index("ix_batch_run_batch_type", "batch_type", text("started_at DESC")),
        {"comment": "배치 실행 1회. 수집된 모든 행이 이 run_id 를 들고 다녀 추적 단위가 된다"},
    )


class CrawlHistory(Base):
    """크롤링한 게시글 1건. 같은 글을 다음 배치에서 또 봐도 행은 새로 쌓인다."""

    __tablename__ = "crawl_history"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("batch_run.run_id", ondelete="CASCADE"))
    source_type: Mapped[str] = mapped_column(String(50))
    source_url: Mapped[str] = mapped_column(String(1000))
    # 본문 SHA-256. 이전 run 과 같은 해시면 파싱을 건너뛴다.
    page_hash: Mapped[str] = mapped_column(String(64), comment="본문 SHA-256. 이전 run 과 같은 해시면 파싱을 건너뛴다")
    has_offer: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[BatchRun] = relationship(back_populates="crawl_histories")

    # run 간 재수집을 허용해야 하므로 UNIQUE 가 아니라 조회용 인덱스로 둔다
    __table_args__ = (
        Index("ix_crawl_history_page_hash", "page_hash"),
        Index("ix_crawl_history_run_id", "run_id"),
        {"comment": "크롤링한 게시글 1건. 같은 글을 다음 배치에서 또 봐도 행은 새로 쌓인다"},
    )
