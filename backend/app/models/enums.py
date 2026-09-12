"""DB CHECK 제약과 애플리케이션이 **같은 목록**을 보게 하는 값 집합.

여기 없는 값은 DB 가 INSERT 를 거부한다.
LLM 파싱 프롬프트나 API 검증도 이 목록을 그대로 가져다 쓴다.
목록을 늘리려면 마이그레이션이 필요하다 - 그게 의도다.
"""

INSTITUTION_TYPES = ("은행", "저축은행", "신협")
PRODUCT_TYPES = ("예금", "적금", "예탁금")

SOCIAL_PROVIDERS = ("GOOGLE", "KAKAO", "NAVER")
SOCIAL_CARE_CATEGORIES = ("다자녀", "한부모", "다문화", "신혼부부", "탈북자")

# MATURITY = 만기일 지난 UserHolding 을 만기 처리하는 일배치.
# 사용자가 앱에 안 들어와도 돌아야 하므로 배치가 필요하다.
BATCH_TYPES = ("COLLECT", "CRAWL", "VERIFY", "PARSE", "MATURITY")
BATCH_STATUSES = ("RUNNING", "SUCCESS", "FAILED", "PARTIAL")

OFFER_SOURCE_TYPES = ("지역은행공식", "커뮤니티")
VERIFICATION_STATUSES = ("PENDING", "VERIFIED", "REJECTED")

PRODUCT_SOURCES = ("OFFICIAL", "SPECIAL")
JOIN_CHANNELS = ("비대면", "영업점", "전체")
PARSE_STATUSES = ("PENDING", "PARSED", "FAILED")

RATE_TYPES = ("단리", "복리")
RESERVE_TYPES = ("해당없음", "정액적립식", "자유적립식")

THRESHOLD_UNITS = ("KRW", "COUNT", "MONTH")
CONDITION_VERIFY_STATUSES = ("EXACT", "MISSING", "EXCESS")
CONFIDENCE_BADGES = ("확인됨", "검수대기")

PORTFOLIO_TYPES = ("단순형", "균형형", "최대형")
PORTFOLIO_STATUSES = ("진행중", "완료")
HOLDING_STATUSES = ("유지중", "만기")

# condition_type 은 아직 목록 미확정이라 CHECK 를 걸지 않았다.
# 확정되면 여기에 튜플을 추가하고 product_condition / user_profile_extra 양쪽에 CHECK 를 건다.


def one_of(column: str, values: tuple[str, ...]) -> str:
    """CHECK (col IN ('a','b')) 의 본문을 만든다."""
    joined = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({joined})"


def one_of_or_null(column: str, values: tuple[str, ...]) -> str:
    """NULL 을 허용하는 버전."""
    return f"{column} IS NULL OR {one_of(column, values)}"
