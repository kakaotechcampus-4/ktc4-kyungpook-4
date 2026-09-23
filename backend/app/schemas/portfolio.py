"""포트폴리오 추천/선택 응답 스키마."""

from pydantic import BaseModel


class PortfolioProductOut(BaseModel):
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
    reason: str


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
