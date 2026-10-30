"""조회 프로필 - 상담 1건이 1행. 사용자가 다시 조회하면 새 행이 쌓인다."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import CONDITION_TYPES, SOCIAL_CARE_CATEGORIES, TAX_EXEMPT_CATEGORIES, one_of
from app.models.user import AppUser


class UserProfile(Base):
    __tablename__ = "user_profile"

    profile_id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.user_id", ondelete="CASCADE"))
    capital: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    monthly_saving: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    period_months: Mapped[int] = mapped_column(Integer)
    # 값 집합 미확정. 확정되면 enums 에 추가하고 CHECK 를 건다.
    withdraw_flexibility: Mapped[str | None] = mapped_column(
        String(20), comment="중도인출 가능성. 값 집합은 기획 확정 후 CHECK 추가"
    )
    main_bank_code: Mapped[str | None] = mapped_column(
        String(20), ForeignKey("institution.institution_code", ondelete="SET NULL")
    )
    region: Mapped[str | None] = mapped_column(String(50))
    # 만 나이 계산에 필요해 원본 보관. 청년·노인 우대조건 판정에 쓴다.
    birth_date: Mapped[date | None] = mapped_column(
        Date, comment="만 나이 계산에 필요해 원본 보관. 청년·노인 우대조건 판정에 쓴다"
    )
    # None = 아직 물어보지 않음 / 확인 불가
    salary_transfer: Mapped[bool | None] = mapped_column(Boolean, comment="NULL = 아직 물어보지 않음 / 확인 불가")
    auto_transfer: Mapped[bool | None] = mapped_column(Boolean)
    monthly_card_usage: Mapped[int | None] = mapped_column(BigInteger)
    # 이 조회 건에서 받은 동의 기록. 법적 기준은 AppUser.marketing_consent 다.
    marketing_consent: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        comment="이 조회 건에서 받은 동의 기록. 계정 단위 최신 동의는 app_user.marketing_consent 를 본다",
    )
    app_install: Mapped[bool | None] = mapped_column(Boolean)
    savings_auto_transfer: Mapped[bool | None] = mapped_column(
        Boolean, comment="적금 납입을 자동이체로 걸 수 있음. NULL = 모름"
    )
    pension_transfer: Mapped[bool | None] = mapped_column(
        Boolean, comment="연금 수령 계좌를 옮길 수 있음. 연금수령 우대조건 판정용. NULL = 모름"
    )
    coop_insurance: Mapped[bool | None] = mapped_column(
        Boolean,
        comment="공제(새마을금고·신협 등) 가입 실적이 있거나 가입 의사가 있음. 공제가입 우대조건 판정용. NULL = 모름",
    )
    accepts_membership: Mapped[bool | None] = mapped_column(
        Boolean,
        comment="신협·새마을금고 조합원 가입(출자금 납입) 의향. 예탁금 가입 자격 판정에 쓴다. NULL = 미확인",
    )
    # 조합 예탁금 감면 세율 판정 (조세특례제한법 제89조의3). 계산은 services/tax.py.
    coop_tax_eligible: Mapped[bool | None] = mapped_column(
        Boolean,
        comment="총급여 7천만원(종합소득 6천만원) 이하 여부. 조합 예탁금 감면 세율이 갈린다. NULL = 모름(초과로 계산)",
    )
    coop_exempt_used: Mapped[int | None] = mapped_column(
        BigInteger,
        comment="다른 조합에 이미 감면으로 넣어 둔 예탁금(원). 1인당 3천만원 한도에서 뺀다. NULL = 모름(0 으로 계산)",
    )
    tax_exempt_used: Mapped[int] = mapped_column(
        BigInteger, server_default=text("0"), comment="올해 이미 사용한 비과세 한도(원)"
    )
    # 위 컬럼들은 답을 해석한 결과다. 해석 규칙이 바뀌어도 다시 계산할 수 있게 원문을 같이 둔다.
    answers: Mapped[dict | None] = mapped_column(
        JSONB, comment="STEP2·3 원문 답변(앱 선택지 문구 그대로). 해석 규칙이 바뀌어도 다시 계산할 수 있게 보관"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[AppUser] = relationship(back_populates="profiles")
    banks: Mapped[list["UserProfileBank"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", passive_deletes=True
    )
    tax_exempts: Mapped[list["UserProfileTaxExempt"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", passive_deletes=True
    )
    social_cares: Mapped[list["UserProfileSocial"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", passive_deletes=True
    )
    extras: Mapped[list["UserProfileExtra"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("period_months > 0", name="period_months"),
        CheckConstraint(
            "capital >= 0 AND monthly_saving >= 0 AND tax_exempt_used >= 0"
            " AND (monthly_card_usage IS NULL OR monthly_card_usage >= 0)"
            " AND (coop_exempt_used IS NULL OR coop_exempt_used >= 0)",
            name="amounts",
        ),
        # 목돈도 월 저축액도 0 이면 배분할 게 없다
        CheckConstraint("capital > 0 OR monthly_saving > 0", name="has_money"),
        Index("ix_user_profile_user_id", "user_id", text("created_at DESC")),
        {"comment": "조회 1건의 입력값 스냅샷. 사용자가 다시 조회하면 새 행이 쌓인다"},
    )


class UserProfileBank(Base):
    """보유(거래 가능) 은행 복수선택."""

    __tablename__ = "user_profile_bank"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user_profile.profile_id", ondelete="CASCADE"))
    institution_code: Mapped[str] = mapped_column(String(20), ForeignKey("institution.institution_code"))

    profile: Mapped[UserProfile] = relationship(back_populates="banks")

    __table_args__ = (
        UniqueConstraint("profile_id", "institution_code"),
        {"comment": "보유(거래 가능) 은행 복수선택"},
    )


class UserProfileTaxExempt(Base):
    """비과세 대상 항목 복수선택 (청년/노인/장애인 등)."""

    __tablename__ = "user_profile_tax_exempt"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user_profile.profile_id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(50))

    profile: Mapped[UserProfile] = relationship(back_populates="tax_exempts")

    __table_args__ = (
        CheckConstraint(one_of("category", TAX_EXEMPT_CATEGORIES), name="category"),
        UniqueConstraint("profile_id", "category"),
        {"comment": "비과세 대상 항목 복수선택 (청년/노인/장애인 등)"},
    )


class UserProfileSocial(Base):
    """사회적 배려 대상 복수선택. 우대금리 가산 판단에 쓴다."""

    __tablename__ = "user_profile_social"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user_profile.profile_id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(20))

    profile: Mapped[UserProfile] = relationship(back_populates="social_cares")

    __table_args__ = (
        CheckConstraint(one_of("category", SOCIAL_CARE_CATEGORIES), name="category"),
        UniqueConstraint("profile_id", "category"),
        {"comment": "사회적 배려 대상 복수선택. 우대금리 가산 판단에 쓴다"},
    )


class UserProfileExtra(Base):
    """고정 문항으로 못 채운 우대조건을 챗봇이 되물은 기록."""

    __tablename__ = "user_profile_extra"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user_profile.profile_id", ondelete="CASCADE"))
    # 어느 상품의 어느 조건에 대한 답인지. '기타' 조건은 상품마다 내용이 달라 condition_type 만으로는 구분이 안 된다.
    # FK 를 걸지 않는다 - ERD 재임포트로 조건 ID 가 바뀌거나 사라질 수 있고, 답변은 조회 1건 안에서만 쓴다.
    condition_id: Mapped[str] = mapped_column(
        String(64),
        comment="챗봇이 물어본 우대조건 product_condition.condition_id. FK 없음 - ERD 재임포트로 바뀔 수 있다",
    )
    # ProductCondition.condition_type 과 반드시 같은 어휘를 쓴다.
    # 어긋나면 에러 없이 우대금리만 조용히 누락된다.
    condition_type: Mapped[str] = mapped_column(
        String(50),
        comment="product_condition.condition_type 과 반드시 같은 어휘를 쓴다. 어긋나면 우대금리가 조용히 누락된다",
    )
    question_text: Mapped[str] = mapped_column(Text)
    answer_value: Mapped[str | None] = mapped_column(String(255))
    raw_answer: Mapped[str | None] = mapped_column(
        Text,
        comment="사용자가 입력한 원문 답변. answer_value 는 이것을 해석한 결과(true/false)",
    )
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped[UserProfile] = relationship(back_populates="extras")

    __table_args__ = (
        CheckConstraint(one_of("condition_type", CONDITION_TYPES), name="condition_type"),
        # 답을 받았으면 시각도 있어야 한다
        CheckConstraint("answer_value IS NULL OR answered_at IS NOT NULL", name="answered"),
        # 조회 1건에서 같은 조건의 답은 하나만 둔다. 다시 답하면 덮어쓴다
        UniqueConstraint("profile_id", "condition_id"),
        Index("ix_user_profile_extra_profile_id", "profile_id"),
        {"comment": "고정 문항으로 못 채운 우대조건을 챗봇이 되물은 기록"},
    )
