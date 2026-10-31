"""포트폴리오 추천/선택 응답 스키마."""

from pydantic import BaseModel


class AppliedConditionOut(BaseModel):
    """이 상품 금리에 반영했다고 본 우대조건. AI Summary 가 '해야 할 일'을 만드는 데도 쓴다."""

    condition_type: str
    bonus_rate: float  # 실제로 가산한 %p
    threshold_value: int | None
    threshold_unit: str | None  # 만원 / 회 / 개월 ...
    already_met: bool  # True = 이미 충족(할 일 아님), False = 새로 해야 함


class PortfolioProductOut(BaseModel):
    institution_code: str  # 기존/신규 은행 판정은 이름이 아니라 코드로 한다
    institution_name: str
    product_name: str
    term_months: int
    base_rate: float  # 기본금리
    interest_rate: float  # 실효금리 = 기본금리 + 이 안에서 인정한 우대폭 (최고금리 상한)
    allocated_amount: int  # 예금이면 원금, 적금이면 월 납입액
    after_tax_interest: int  # 세후 이자(원). 원금은 포함하지 않는다
    applied_conditions: list[AppliedConditionOut]


class PortfolioOptionOut(BaseModel):
    tier: str  # 단순형 | 균형형 | 최대형 | 안정형
    products: list[PortfolioProductOut]
    after_tax_total: int  # 세후 이자 합계(원). 원금은 포함하지 않는다
    reason: str  # AI Summary 가 만든 추천 이유. AI 실패 시 계산값만으로 만든 기본 문구
    extra_vs_baseline: int | None  # 단일형 대비 세후 이자 증가분(원). 단일형이 없으면 None
    extra_vs_simple: int | None  # 단순형 대비 세후 이자 증가분(원). 균형형·최대형만, 나머지는 None
    new_bank_count: int  # 이 안을 실행하려면 새로 가입해야 하는 기관 수
    required_actions: list[str]  # 우대금리를 받으려고 새로 해야 하는 일
    tax_saving_won: int  # 조합 예탁금 감면으로 일반과세(15.4%)보다 줄어든 세금(원)
    over_comprehensive_tax: bool  # 일반과세 이자가 2천만원을 넘어 금융소득종합과세 대상이 될 수 있음


class BaselineOut(BaseModel):
    """단일형: 주거래은행 상품 하나에 전액을 넣었을 때. 추천안이 아니라 비교 기준선이다."""

    institution_name: str
    product_name: str  # 예금·적금을 모두 넣으면 두 상품명을 ' + ' 로 잇는다
    products: list[PortfolioProductOut]
    after_tax_total: int
    exceeds_protection: bool  # 한 은행에 원금 1억원 초과 -> 초과분은 예금자보호를 받지 못함


class PortfolioRecommendRequest(BaseModel):
    profile_id: int


class PortfolioRecommendResponse(BaseModel):
    options: list[PortfolioOptionOut]
    baseline: BaselineOut | None  # 주거래은행을 모르거나 그 은행 상품이 없으면 null


class PortfolioSelectRequest(BaseModel):
    profile_id: int
    tier: str


class PortfolioOut(BaseModel):
    portfolio_id: int
    tier: str
    status: str
    after_tax_total: int | None
