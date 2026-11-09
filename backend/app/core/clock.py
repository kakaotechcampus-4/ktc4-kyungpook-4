"""서비스의 '오늘'. 사용자가 한국에 있어서 한국 시간 기준으로 센다.

서버(컨테이너)는 UTC 라 date.today() 를 쓰면 한국 시간 0~9시에는 전날이 된다.
한국은 서머타임이 없어 tzdata 없이 고정 +09:00 으로 충분하다.
"""

from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9), "KST")


def today() -> date:
    return datetime.now(KST).date()


def kst_date(moment: datetime) -> date:
    """DB 의 timestamptz(UTC) 를 한국 날짜로."""
    return moment.astimezone(KST).date()
