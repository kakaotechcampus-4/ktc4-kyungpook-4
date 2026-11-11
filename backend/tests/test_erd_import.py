"""AI 산출물 임포터의 작은 규칙들 (DB 없이)."""

from app.importers.erd_import import display_name, product_id_of


def test_display_name_joins_broken_lines():
    assert display_name("스마일드림 \n정기예금\n(개인/선이자\n지급식)") == "스마일드림 정기예금 (개인/선이자 지급식)"
    assert display_name("KB Star 정기예금") == "KB Star 정기예금"


def test_product_id_uses_raw_name():
    # 화면용 이름만 정리하고 키는 원문으로 만든다. 키가 바뀌면 기존 가입 내역과의 링크가 끊긴다
    raw = "J정기예금\n(만기지급식)"
    assert product_id_of("BANK-1-01", raw) != product_id_of("BANK-1-01", display_name(raw))
