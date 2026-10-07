"""포트폴리오 추천/선택 응답 스키마."""

from pydantic import BaseModel


class PortfolioProductOut(BaseModel):
    institution_code: str  # 기존/신규 은행 판정은 이름이 아니라 코드로 한다
    institution_name: str
    product_name: str
    term_months: int
    interest_rate: float
    allocated_amount: int
    after_tax_interest: int


class PortfolioOptionOut(BaseModel):
    tier: str  # 단순형 | 균형형 | 최대형
    products: list[PortfolioProductOut]
    after_tax_total: int
    reason: str  # AI Summary 가 만든 추천 이유. AI 실패 시 계산값만으로 만든 기본 문구
    extra_vs_simple: int | None  # 단순형 대비 세후 이자 증가분(원). 단순형 자신은 None
    new_bank_count: int  # 이 안을 실행하려면 새로 가입해야 하는 은행 수


class PortfolioRecommendRequest(BaseModel):
    profile_id: int


class PortfolioRecommendResponse(BaseModel):
    options: list[PortfolioOptionOut]


class PortfolioSelectRequest(BaseModel):
    profile_id: int
    tier: str


class PortfolioOut(BaseModel):
    portfolio_id: int
    tier: str
    status: str
    after_tax_total: int | None
