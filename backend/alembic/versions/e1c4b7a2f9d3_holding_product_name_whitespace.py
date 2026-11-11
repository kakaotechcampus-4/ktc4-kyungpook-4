"""user_holding.product_name 의 줄바꿈·연속 공백을 한 칸으로

공시 상품명에 줄바꿈이 섞여 와('J정기예금\\n(만기지급식)') 캘린더·결과 화면 중간에서 줄이 끊겼다.
임포터는 이제 정리해서 넣고(display_name), 이미 가입 시점에 스냅샷으로 저장된 이름도 같이 정리한다.

Revision ID: e1c4b7a2f9d3
Revises: d2f7a9c3e1b5
Create Date: 2026-11-11 03:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e1c4b7a2f9d3"
down_revision: str | Sequence[str] | None = "d2f7a9c3e1b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        r"UPDATE user_holding SET product_name = btrim(regexp_replace(product_name, '\s+', ' ', 'g')) "
        r"WHERE product_name ~ '\s\s|[\n\r\t]' OR product_name <> btrim(product_name)"
    )


def downgrade() -> None:
    # 원래 줄바꿈 위치는 남아 있지 않다. 되돌릴 필요도 없는 표시용 정리라 그대로 둔다.
    pass
