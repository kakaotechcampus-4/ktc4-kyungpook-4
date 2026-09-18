"""Extraction(호출 A) 결과 스키마 - 우대조건 원문(spcl_cnd)을 구조화한 결과."""
from typing import List, Optional
from pydantic import BaseModel


class PreferentialCondition(BaseModel):
    """개별 우대조건 하나."""
    description: str  # 조건 설명 (예: "급여이체 실적 보유")
    # [v8: Optional로 변경] 원래 필수(float)였는데, 실제 285건 중 7건이 "외부 코드/쿠폰
    # 입력에 따라 달라짐", "고객 속성(자녀수/임신·출산 여부 등)에 따라 달라짐", "전체
    # 범위(0.1~0.5%)만 있고 개별 항목별 %가 원문에 안 쪼개져 있음"처럼 원문 자체에 그
    # 조건 하나만의 구체적 %가 없어서, AI가 null을 주는데 스키마가 이를 거부해 파싱
    # 실패로 떨어졌음. null을 허용해서 저장은 되게 하고(값 없이도 description/
    # condition_type은 남겨서 나중에 챗봇이 활용 가능), 합계 계산(compute_extracted_total)
    # 에서는 0으로 취급하도록 고침 - 지어낸 값보다 "모른다"를 있는 그대로 저장하는 게 맞음.
    bonus_rate: Optional[float] = None  # 이 조건으로 받는 우대금리 (%p 단위, 예: 0.2). 원문에 구체적 값이 없으면 null.
    # [v7 추가] 원래는 키워드 매칭(classify_condition_type)으로 채우던 값인데, 그건
    # 정규식 시절의 잔재라서 AI가 뽑은 다른 값들(우대금리/만기/group_id)에 비해 정확도가
    # 떨어짐 - AI가 description을 보고 직접 분류하도록 여기로 옮김. 값은 미리 정해둔
    # 카테고리 중 하나(프롬프트에 목록 있음), 안 맞으면 "기타".
    condition_type: str = "기타"
    applicable_term_months: Optional[int] = None  # 정확히 이 만기(개월)에만 적용하면 그 값
    min_term_months: Optional[int] = None  # "X개월 이상"처럼 하한 조건이면 그 값(해당 만기 이상이면 다 적용)
    max_term_months: Optional[int] = None  # "X개월 이하/까지"처럼 상한 조건이면 그 값
    # -> min_term_months와 max_term_months를 같이 쓰면 "X~Y개월" 범위도 표현 가능
    group_id: Optional[str] = None  # 같은 group_id를 가진 조건들은 서로 대체 관계
    # (하나만 인정, 최댓값만 반영) - 예: 금액/실적/점수/인원수 구간별 조건들, 또는 "최고 X%p"
    # 아래 나열된 ①②③... 조건들. 독립적으로 각자 더해지는 조건이면 비워둠(None).
    # [v9 추가] 그동안 evidence_text(원문 문장) 안에만 텍스트로 남아있던 "이 조건을
    # 충족하려면 넘어야 하는 숫자 기준"을 구조화된 컬럼으로도 뽑음(BE ERD의
    # product_condition.threshold_value/threshold_unit은 처음 설계부터 있었는데, AI
    # 추출 스키마에 대응 필드가 없어서 지금까지 한 번도 채워진 적이 없었음). 목적:
    # 실시간 매칭 로직(사용자가 입력한 값과 이 조건을 비교하는 규칙 기반 코드)이
    # evidence_text를 다시 정규식으로 파싱하지 않고 이 두 컬럼만 보고 바로 비교할 수
    # 있게 하는 것.
    threshold_value: Optional[float] = None  # 조건 충족 기준 숫자 (예: "50만원 이상"
    # -> 50, "월 5회 이상" -> 5). 기준 숫자가 없는 조건(예: "신규고객", "마케팅 동의")
    # 이면 null.
    threshold_unit: Optional[str] = None  # threshold_value의 단위를 원문 표현 그대로
    # (예: "만원", "원", "회", "건", "명", "점", "보"). threshold_value가 null이면
    # 같이 null.


class ExtractionResult(BaseModel):
    """spcl_cnd 원문 하나를 분석한 결과."""
    conditions: List[PreferentialCondition]
    # [v5 추가] 원문에 "최고/최대 우대금리: X%"처럼 개별 조건들을 다 더해도 절대
    # 넘지 못하는 전체 상한이 명시돼 있으면 그 값(%p). 그런 상한 문구가 원문에
    # 없으면 null. (개별 조건이 아니라 이 응답 전체에 대해 한 번만 채움)
    overall_max_bonus_rate: Optional[float] = None