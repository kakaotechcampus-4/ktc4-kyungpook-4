"""특판 파이프라인 제거 + AI 산출물을 손실 없이 담기 위한 조정

[특판 제거]
공시 데이터만으로 상품을 전부 수집할 수 있게 되어, 커뮤니티 특판을 크롤링해 검증하고
상품으로 승격시키는 경로가 통째로 없어졌다. 그 경로에만 쓰이던 테이블 4개를 지운다.
  special_offer / special_offer_option : 특판 후보와 검증 결과
  crawl_history                        : 특판을 찾으려고 긁은 게시글 기록
  institution_alias                    : 크롤링 문자열을 기관 코드로 되돌리던 사전
                                         (공시 산출물은 institution_code 를 직접 준다)
product.offer_id / product.source 도 같이 뺀다. source 는 값이 'OFFICIAL' 하나만 남는다.
batch_type 에서도 CRAWL / VERIFY 가 빠진다.

product_condition.verification_status 는 남긴다. 이름은 비슷하지만 특판 검증이 아니라
'AI 가 뽑은 우대조건이 약관과 맞는가'로 뜻이 다르다.

[AI 산출물 수용]
  - product_option.join_channel : 같은 상품인데 창구와 비대면의 금리가 다른 경우가 있다
    (실측 758건, 예: 정기예탁금 창구 3.20% / 비대면 3.25%). 채널이 product 에만 있으면
    이 차이를 표현할 수 없어 상품 행을 통째로 복제해야 한다.
  - institution.name UNIQUE 제거 : 지역이 다른 동명 새마을금고가 별개 기관이다
    ('우리새마을금고 본점' 8곳). 제약을 두면 이름을 조작해야 하고 그 이름이 화면에 나간다.
  - product_condition.rate_bonus NULL 허용 : 원문에 우대폭이 없는 조건이 421건 있다.
    0 으로 채우면 '가산 0%p' 와 구별되지 않는다.
  - institution_type += 새마을금고 (1,039 기관)
  - condition_type   += 공제가입(2,043) / 연령조건(210)
  - threshold_unit   += WEEK/DAY/HOUR/AGE/SCORE/STEP (519건이 KRW·COUNT·MONTH 로 표현 불가)

Revision ID: b1c4e7a90f32
Revises: 7e09bd091feb
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql.elements import conv

from alembic import op

revision: str = "b1c4e7a90f32"
down_revision: str | Sequence[str] | None = "7e09bd091feb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INSTITUTION_TYPES_OLD = "'은행', '저축은행', '신협'"
CONDITION_TYPES_OLD = (
    "'급여이체', '자동이체', '신규고객', '카드실적', '마케팅동의', '공과금이체', '연금수령', '비대면가입', '기타'"
)
THRESHOLD_UNITS_OLD = "'KRW', 'COUNT', 'MONTH'"
INSTITUTION_TYPES = "'은행', '저축은행', '신협', '새마을금고'"
CONDITION_TYPES = (
    "'급여이체', '자동이체', '신규고객', '카드실적', '마케팅동의', '공과금이체', '연금수령',"
    " '비대면가입', '공제가입', '연령조건', '기타'"
)
THRESHOLD_UNITS = "'KRW', 'COUNT', 'MONTH', 'WEEK', 'DAY', 'HOUR', 'AGE', 'SCORE', 'STEP'"


def _swap_check(table: str, name: str, body: str) -> None:
    """CHECK 은 ALTER 가 없다. 같은 이름으로 지웠다 다시 만든다.

    지울 때는 conv() 로 감싼다. 감싸지 않으면 alembic 이 NAMING_CONVENTION 을 한 번 더
    적용해서 'ck_product_ck_product_source_offer' 같은 이름을 만들고 DROP 이 실패한다.
    만들 때는 반대로 규칙이 이름을 완성하도록 접두사를 뗀 이름을 준다.
    """
    op.drop_constraint(conv(name), table, type_="check")
    op.create_check_constraint(name.removeprefix(f"ck_{table}_"), table, body)


def upgrade() -> None:
    # --- 특판 파이프라인 제거 ------------------------------------------------
    # product 가 special_offer 를 참조하므로 상품 쪽 결합부터 끊는다.
    op.drop_constraint(conv("ck_product_source_offer"), "product", type_="check")
    op.drop_constraint(conv("ck_product_source"), "product", type_="check")
    op.drop_constraint(conv("uq_product_offer_id"), "product", type_="unique")
    op.drop_constraint(conv("fk_product_offer_id_special_offer"), "product", type_="foreignkey")
    op.drop_column("product", "offer_id")
    op.drop_column("product", "source")

    op.drop_table("special_offer_option")  # special_offer 를 참조하므로 먼저
    op.drop_table("special_offer")
    op.drop_table("crawl_history")
    op.drop_table("institution_alias")

    _swap_check("batch_run", "ck_batch_run_batch_type", "batch_type IN ('COLLECT', 'PARSE', 'MATURITY')")

    op.alter_column(
        "product",
        "product_id",
        comment="금융회사코드 + 상품코드 조합. 배치 간 안정적이어야 한다",
        existing_type=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "product",
        "sale_end_date",
        comment="판매 종료 예정일. 공시 상품은 대개 NULL - snapshot_date 가 오래되면 사라진 것으로 본다",
        existing_type=sa.Date(),
        existing_nullable=True,
    )
    op.alter_column(
        "institution",
        "name",
        comment="정식 명칭. 지역이 다른 동명 기관이 있어 UNIQUE 를 걸지 않는다",
        existing_type=sa.String(length=100),
        existing_nullable=False,
    )

    # --- 어휘 확장 -----------------------------------------------------------
    _swap_check("institution", "ck_institution_institution_type", f"institution_type IN ({INSTITUTION_TYPES})")
    _swap_check("product_condition", "ck_product_condition_condition_type", f"condition_type IN ({CONDITION_TYPES})")
    _swap_check("user_profile_extra", "ck_user_profile_extra_condition_type", f"condition_type IN ({CONDITION_TYPES})")
    _swap_check(
        "product_condition",
        "ck_product_condition_threshold_unit",
        f"threshold_unit IS NULL OR threshold_unit IN ({THRESHOLD_UNITS})",
    )

    # --- institution.name UNIQUE 제거 ---------------------------------------
    op.drop_constraint(conv("uq_institution_name"), "institution", type_="unique")

    # --- product_option 에 채널 축 추가 -------------------------------------
    # 기존 행은 채널 구분이 없었으므로 '전체' 로 채워진다.
    op.add_column(
        "product_option",
        sa.Column(
            "join_channel",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'전체'"),
            comment="이 금리가 적용되는 가입 채널. 채널 구분이 없는 상품은 '전체'",
        ),
    )
    op.create_check_constraint("join_channel", "product_option", "join_channel IN ('비대면', '영업점', '전체')")
    op.drop_constraint(conv("uq_product_option_product_id"), "product_option", type_="unique")
    op.create_unique_constraint(
        conv("uq_product_option_product_id"),
        "product_option",
        ["product_id", "period_months", "rate_type", "reserve_type", "join_channel"],
    )
    op.alter_column(
        "product_option",
        "option_id",
        comment="product_id + 기간 + 이자방식 + 적립방식 + 채널 조합으로 결정적으로 생성."
        " 배치가 upsert 해도 user_holding 링크가 유지된다",
        existing_type=sa.String(length=96),
        existing_nullable=False,
    )

    # --- rate_bonus NULL 허용 ------------------------------------------------
    op.alter_column(
        "product_condition",
        "rate_bonus",
        existing_type=sa.Numeric(4, 2),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    """지운 구조를 되돌린다. 테스트 전용 - 운영 롤백 수단이 아니다 (README '마이그레이션 되돌리기').

    구조는 원래대로 돌아오지만 **지워진 행은 돌아오지 않는다.** 특판 테이블 4개는 빈 채로
    다시 만들어진다. 데이터까지 되돌려야 하면 백업을 복원해야 한다.
    """
    # --- 어휘를 좁히기 전에, 좁힌 값으로 들어온 행이 있으면 CHECK 에 걸린다.
    #     되돌리기가 목적이므로 그런 행은 먼저 지운다.
    op.execute("DELETE FROM product_condition WHERE condition_type IN ('공제가입', '연령조건')")
    op.execute("DELETE FROM product_condition WHERE threshold_unit IN ('WEEK', 'DAY', 'HOUR', 'AGE', 'SCORE', 'STEP')")
    op.execute("DELETE FROM user_profile_extra WHERE condition_type IN ('공제가입', '연령조건')")
    op.execute(
        "DELETE FROM product WHERE institution_code IN (SELECT institution_code FROM institution WHERE institution_type = '새마을금고')"
    )
    op.execute("DELETE FROM institution WHERE institution_type = '새마을금고'")

    # --- product_condition.rate_bonus NOT NULL 복구 -------------------------
    # NULL 이 남아 있으면 NOT NULL 로 못 돌아간다. 0 으로 채운다.
    op.execute("UPDATE product_condition SET rate_bonus = 0 WHERE rate_bonus IS NULL")
    op.alter_column(
        "product_condition",
        "rate_bonus",
        existing_type=sa.Numeric(4, 2),
        nullable=False,
        server_default=sa.text("0"),
    )

    # --- product_option 채널 축 제거 ----------------------------------------
    # 채널이 갈린 옵션은 채널을 빼면 (상품, 기간, 이자방식, 적립방식) 이 겹쳐 UNIQUE 에 걸린다.
    # '전체' 가 아닌 행 중 뒤쪽 하나만 남긴다.
    op.execute("""
        DELETE FROM product_option a USING product_option b
        WHERE a.option_id > b.option_id
          AND a.product_id = b.product_id AND a.period_months = b.period_months
          AND a.rate_type = b.rate_type AND a.reserve_type = b.reserve_type
    """)
    op.drop_constraint(conv("uq_product_option_product_id"), "product_option", type_="unique")
    op.create_unique_constraint(
        conv("uq_product_option_product_id"),
        "product_option",
        ["product_id", "period_months", "rate_type", "reserve_type"],
    )
    op.drop_constraint(conv("ck_product_option_join_channel"), "product_option", type_="check")
    op.drop_column("product_option", "join_channel")
    op.alter_column(
        "product_option",
        "option_id",
        comment="product_id + 기간 + 이자방식 조합으로 결정적으로 생성."
        " 배치가 upsert 해도 user_holding 링크가 유지된다",
        existing_type=sa.String(length=96),
        existing_nullable=False,
    )

    # --- institution.name UNIQUE 복구 ---------------------------------------
    # 이름이 겹치는 기관이 남아 있으면 UNIQUE 를 못 건다. 코드 뒤쪽을 지운다.
    op.execute("""
        DELETE FROM institution a USING institution b
        WHERE a.institution_code > b.institution_code AND a.name = b.name
    """)
    op.create_unique_constraint(conv("uq_institution_name"), "institution", ["name"])
    op.alter_column(
        "institution",
        "name",
        comment="정식 명칭 1개. 표기 변형은 institution_alias 로 흡수한다",
        existing_type=sa.String(length=100),
        existing_nullable=False,
    )

    # --- 어휘 복구 -----------------------------------------------------------
    _swap_check("institution", "ck_institution_institution_type", f"institution_type IN ({INSTITUTION_TYPES_OLD})")
    _swap_check(
        "product_condition", "ck_product_condition_condition_type", f"condition_type IN ({CONDITION_TYPES_OLD})"
    )
    _swap_check(
        "user_profile_extra", "ck_user_profile_extra_condition_type", f"condition_type IN ({CONDITION_TYPES_OLD})"
    )
    _swap_check(
        "product_condition",
        "ck_product_condition_threshold_unit",
        f"threshold_unit IS NULL OR threshold_unit IN ({THRESHOLD_UNITS_OLD})",
    )
    _swap_check(
        "batch_run", "ck_batch_run_batch_type", "batch_type IN ('COLLECT', 'CRAWL', 'VERIFY', 'PARSE', 'MATURITY')"
    )

    # --- 특판 테이블 복구 (빈 테이블로 다시 만들어진다) ----------------------
    op.create_table(
        "institution_alias",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("institution_code", sa.String(length=20), nullable=False),
        sa.Column("alias", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_code"],
            ["institution.institution_code"],
            name=op.f("fk_institution_alias_institution_code_institution"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institution_alias")),
        sa.UniqueConstraint("alias", name=op.f("uq_institution_alias_alias")),
        comment='크롤링 문자열을 코드로 되돌리는 사전. "KB국민", "국민은행", "국민" 을 모두 같은 코드로 보낸다',
    )
    op.create_table(
        "crawl_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column(
            "page_hash",
            sa.String(length=64),
            nullable=False,
            comment="본문 SHA-256. 이전 run 과 같은 해시면 파싱을 건너뛴다",
        ),
        sa.Column("has_offer", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["batch_run.run_id"], name=op.f("fk_crawl_history_run_id_batch_run"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crawl_history")),
        comment="크롤링한 게시글 1건. 같은 글을 다음 배치에서 또 봐도 행은 새로 쌓인다",
    )
    op.create_table(
        "special_offer",
        sa.Column(
            "offer_id",
            sa.String(length=64),
            nullable=False,
            comment="출처 URL + 상품명 해시 등으로 만든 애플리케이션 발급 ID",
        ),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "crawl_history_id", sa.BigInteger(), nullable=True, comment="이 특판을 발견한 크롤링 건. 원문 추적용"
        ),
        sa.Column(
            "claimed_institution",
            sa.String(length=100),
            nullable=False,
            comment="커뮤니티 글에 적힌 기관명 원문. 검증 단계에서 institution_alias 로 코드를 찾아 붙인다",
        ),
        sa.Column("institution_type", sa.String(length=20), nullable=True),
        sa.Column("product_type", sa.String(length=20), nullable=True),
        sa.Column("claimed_product_name", sa.String(length=200), nullable=True),
        sa.Column("claimed_base_rate", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column(
            "claimed_max_rate",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
            comment="커뮤니티 글이 주장한 금리. 검증 전 값이라 노출 금지",
        ),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=20), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column(
            "institution_code",
            sa.String(length=20),
            nullable=True,
            comment="기관 매칭에 성공한 뒤 채워진다. NULL 이면 아직 미해결",
        ),
        sa.Column("matched_product_name", sa.String(length=200), nullable=True),
        sa.Column("verified_amount_cap", sa.BigInteger(), nullable=True),
        sa.Column("verified_terms_text", sa.Text(), nullable=True),
        sa.Column("verify_source_url", sa.String(length=1000), nullable=True),
        sa.Column("verification_status", sa.String(length=20), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("rejected_reason", sa.String(length=200), nullable=True),
        sa.Column("verify_attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_verify_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "institution_type IS NULL OR institution_type IN ('은행', '저축은행', '신협')",
            name=op.f("ck_special_offer_institution_type"),
        ),
        sa.CheckConstraint(
            "product_type IS NULL OR product_type IN ('예금', '적금', '예탁금')",
            name=op.f("ck_special_offer_product_type"),
        ),
        sa.CheckConstraint(
            "source_type IS NULL OR source_type IN ('지역은행공식', '커뮤니티')",
            name=op.f("ck_special_offer_source_type"),
        ),
        sa.CheckConstraint(
            "verification_status <> 'REJECTED' OR rejected_reason IS NOT NULL",
            name=op.f("ck_special_offer_rejected_reason"),
        ),
        sa.CheckConstraint(
            "verification_status <> 'VERIFIED' OR (verified_at IS NOT NULL AND verify_source_url IS NOT NULL AND institution_code IS NOT NULL)",
            name=op.f("ck_special_offer_verified_evidence"),
        ),
        sa.CheckConstraint(
            "verification_status IN ('PENDING', 'VERIFIED', 'REJECTED')",
            name=op.f("ck_special_offer_verification_status"),
        ),
        sa.CheckConstraint(
            "(claimed_base_rate IS NULL OR claimed_base_rate >= 0) AND (claimed_max_rate IS NULL OR claimed_base_rate IS NULL OR claimed_max_rate >= claimed_base_rate)",
            name=op.f("ck_special_offer_rates"),
        ),
        sa.CheckConstraint("verify_attempt_count >= 0", name=op.f("ck_special_offer_verify_attempt_count")),
        sa.ForeignKeyConstraint(
            ["crawl_history_id"],
            ["crawl_history.id"],
            name=op.f("fk_special_offer_crawl_history_id_crawl_history"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["institution_code"],
            ["institution.institution_code"],
            name=op.f("fk_special_offer_institution_code_institution"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["batch_run.run_id"], name=op.f("fk_special_offer_run_id_batch_run"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("offer_id", name=op.f("pk_special_offer")),
        comment="커뮤니티/지역은행에서 발견한 특판 후보. 검증 전에는 사용자에게 노출하지 않는다",
    )
    op.create_table(
        "special_offer_option",
        sa.Column(
            "offer_option_id",
            sa.String(length=96),
            nullable=False,
            comment="offer_id + 기간 + 이자방식 조합. 승격 시 product_option 으로 1:1 옮겨간다",
        ),
        sa.Column("offer_id", sa.String(length=64), nullable=False),
        sa.Column("period_months", sa.Integer(), nullable=False),
        sa.Column("rate_type", sa.String(length=10), server_default=sa.text("'단리'"), nullable=False),
        sa.Column("reserve_type", sa.String(length=20), server_default=sa.text("'해당없음'"), nullable=False),
        sa.Column("base_rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("max_rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.CheckConstraint("rate_type IN ('단리', '복리')", name=op.f("ck_special_offer_option_rate_type")),
        sa.CheckConstraint(
            "reserve_type IN ('해당없음', '정액적립식', '자유적립식')",
            name=op.f("ck_special_offer_option_reserve_type"),
        ),
        sa.CheckConstraint("base_rate >= 0 AND max_rate >= base_rate", name=op.f("ck_special_offer_option_rates")),
        sa.CheckConstraint("period_months > 0", name=op.f("ck_special_offer_option_period_months")),
        sa.ForeignKeyConstraint(
            ["offer_id"],
            ["special_offer.offer_id"],
            name=op.f("fk_special_offer_option_offer_id_special_offer"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("offer_option_id", name=op.f("pk_special_offer_option")),
        sa.UniqueConstraint(
            "offer_id", "period_months", "rate_type", "reserve_type", name=op.f("uq_special_offer_option_offer_id")
        ),
        comment="은행 사이트에서 확인한 특판의 기간별 금리. 특판도 12/24개월 식으로 여러 기간을 줄 수 있다",
    )
    op.create_index("ix_crawl_history_page_hash", "crawl_history", ["page_hash"], unique=False)
    op.create_index("ix_crawl_history_run_id", "crawl_history", ["run_id"], unique=False)
    op.create_index("ix_special_offer_run_id", "special_offer", ["run_id"], unique=False)
    op.create_index(
        "ix_special_offer_verification_status",
        "special_offer",
        ["verification_status", sa.literal_column("discovered_at DESC")],
        unique=False,
    )
    op.create_index("ix_special_offer_option_offer_id", "special_offer_option", ["offer_id"], unique=False)

    # --- product 의 특판 결합부 복구 -----------------------------------------
    # source 는 NOT NULL 이라 기존 행을 채울 값이 필요하다. 채운 뒤 기본값을 뗀다.
    op.add_column("product", sa.Column("offer_id", sa.String(length=64), nullable=True))
    op.add_column(
        "product", sa.Column("source", sa.String(length=10), nullable=False, server_default=sa.text("'OFFICIAL'"))
    )
    op.alter_column(
        "product", "source", server_default=None, existing_type=sa.String(length=10), existing_nullable=False
    )
    op.create_foreign_key(
        conv("fk_product_offer_id_special_offer"),
        "product",
        "special_offer",
        ["offer_id"],
        ["offer_id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(conv("uq_product_offer_id"), "product", ["offer_id"])
    op.create_check_constraint("source", "product", "source IN ('OFFICIAL', 'SPECIAL')")
    op.create_check_constraint(
        "source_offer",
        "product",
        "(source = 'SPECIAL' AND offer_id IS NOT NULL) OR (source = 'OFFICIAL' AND offer_id IS NULL)",
    )
    op.alter_column(
        "product",
        "product_id",
        comment="공시 = 금융회사코드 + 상품코드 조합, 특판 = 'SP-' || offer_id. 배치 간 안정적이어야 한다",
        existing_type=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "product",
        "sale_end_date",
        comment="판매 종료 예정일. 특판은 채워지고 공시 상품은 대개 NULL - 그쪽은 snapshot_date 가 오래되면 사라진 것으로 본다",
        existing_type=sa.Date(),
        existing_nullable=True,
    )
