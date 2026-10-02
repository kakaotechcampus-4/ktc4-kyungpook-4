"""금융기관 마스터."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

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
    name: Mapped[str] = mapped_column(
        String(100), comment="정식 명칭. 지역이 다른 동명 기관이 있어 UNIQUE 를 걸지 않는다"
    )
    institution_type: Mapped[str] = mapped_column(String(20))
    region: Mapped[str | None] = mapped_column(String(50), comment="지역은행·신협의 영업 지역. 전국구면 NULL")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    # name 에 UNIQUE 를 걸지 않는다. 지역이 다른 동명 새마을금고('우리새마을금고 본점' 8곳 등)가
    # 실제로 존재하는 별개 기관이라, 제약을 걸면 이름을 조작해야 하고 그 이름이 화면에 그대로 나간다.
    __table_args__ = (
        CheckConstraint(one_of("institution_type", INSTITUTION_TYPES), name="institution_type"),
        {"comment": "금융기관 마스터. 기관을 가리키는 모든 곳은 이름이 아니라 이 코드를 쓴다"},
    )
