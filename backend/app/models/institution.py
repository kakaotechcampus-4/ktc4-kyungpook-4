"""금융기관 마스터."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import INSTITUTION_TYPES, one_of


class Institution(Base):
    """기관을 가리키는 모든 곳은 이름이 아니라 이 코드를 쓴다."""

    __tablename__ = "institution"

    institution_code: Mapped[str] = mapped_column(
        String(20),
        primary_key=True,
        comment="금감원 금융회사코드(fin_co_no). 공시에 없는 기관은 자체 코드 부여",
    )
    name: Mapped[str] = mapped_column(String(100), comment="정식 명칭 1개. 표기 변형은 institution_alias 로 흡수한다")
    institution_type: Mapped[str] = mapped_column(String(20))
    region: Mapped[str | None] = mapped_column(String(50), comment="지역은행·신협의 영업 지역. 전국구면 NULL")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    aliases: Mapped[list["InstitutionAlias"]] = relationship(
        back_populates="institution", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("name"),
        CheckConstraint(one_of("institution_type", INSTITUTION_TYPES), name="institution_type"),
        {"comment": "금융기관 마스터. 기관을 가리키는 모든 곳은 이름이 아니라 이 코드를 쓴다"},
    )


class InstitutionAlias(Base):
    """크롤링 문자열을 코드로 되돌리는 사전. "KB국민", "국민은행" 을 같은 코드로 보낸다."""

    __tablename__ = "institution_alias"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    institution_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("institution.institution_code", ondelete="CASCADE")
    )
    alias: Mapped[str] = mapped_column(String(100))

    institution: Mapped[Institution] = relationship(back_populates="aliases")

    # 한 표기가 두 기관을 가리키면 매칭이 불가능해진다
    __table_args__ = (
        UniqueConstraint("alias"),
        {"comment": '크롤링 문자열을 코드로 되돌리는 사전. "KB국민", "국민은행", "국민" 을 모두 같은 코드로 보낸다'},
    )
