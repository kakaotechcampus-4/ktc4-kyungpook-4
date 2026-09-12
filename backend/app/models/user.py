"""서비스 계정과 소셜 로그인 연결."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import SOCIAL_PROVIDERS, one_of

if TYPE_CHECKING:
    # profile.py 가 이 파일을 import 하므로 런타임에 가져오면 순환이 된다.
    # 타입 검사할 때만 읽히면 충분하다.
    from app.models.profile import UserProfile


class AppUser(Base):
    """소셜 로그인으로만 생성된다."""

    __tablename__ = "app_user"

    user_id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255), comment="대표 이메일. 소셜사가 미제공하면 NULL")
    # 계정 단위 마케팅 동의. 발송 여부는 항상 이 값만 본다.
    marketing_consent: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        comment="계정 단위 마케팅 동의. 법적 기준은 이 값이며 user_profile 쪽은 조회 시점 기록일 뿐이다",
    )
    consent_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="마케팅 동의를 마지막으로 변경한 시각"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    social_accounts: Mapped[list["SocialAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    profiles: Mapped[list["UserProfile"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    # 이메일은 소셜사마다 중복될 수 있어 UNIQUE 를 걸지 않는다
    __table_args__ = (
        Index("ix_app_user_email", "email", postgresql_where=text("email IS NOT NULL")),
        {"comment": "서비스 계정. 소셜 로그인으로만 생성된다"},
    )


class SocialAccount(Base):
    """한 계정에 여러 provider 를 연결할 수 있다."""

    __tablename__ = "social_account"

    social_id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.user_id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(20))
    provider_user_id: Mapped[str] = mapped_column(String(255), comment="소셜사가 발급한 고유 ID (sub/id)")
    provider_email: Mapped[str | None] = mapped_column(String(255))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[AppUser] = relationship(back_populates="social_accounts")

    __table_args__ = (
        CheckConstraint(one_of("provider", SOCIAL_PROVIDERS), name="provider"),
        # 같은 소셜 계정이 두 명에게 붙는 것을 막는다 (로그인 식별의 근거)
        UniqueConstraint("provider", "provider_user_id"),
        # 한 사용자가 같은 provider 를 두 번 연결하지 못하게 한다
        UniqueConstraint("user_id", "provider"),
        {"comment": "소셜 로그인 연결. 한 계정에 여러 provider 연결 가능"},
    )
