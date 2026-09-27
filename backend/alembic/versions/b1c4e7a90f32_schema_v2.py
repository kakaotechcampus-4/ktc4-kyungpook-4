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
    _swap_check(
        "product_condition", "ck_product_condition_condition_type", f"condition_type IN ({CONDITION_TYPES})"
    )
    _swap_check(
        "user_profile_extra", "ck_user_profile_extra_condition_type", f"condition_type IN ({CONDITION_TYPES})"
    )
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
    """되돌릴 수 없다.

    테이블 4개를 지우면서 그 안의 행도 같이 사라진다. 여기서 빈 테이블을 다시 만들어 주면
    '되돌렸다'고 착각하게 되지만 데이터는 돌아오지 않는다. 구조까지 되돌려야 한다면
    7e09bd091feb 로 새로 올리고 백업을 복원하는 편이 안전하다.
    """
    raise NotImplementedError("특판 테이블 4개를 지우는 마이그레이션이라 되돌릴 수 없다. 백업에서 복원할 것")
