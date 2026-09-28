"""포트폴리오 추천/선택, 만기 캘린더 API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.profile import UserProfile
from app.schemas.calendar import CalendarEventOut
from app.schemas.portfolio import (
    PortfolioOut,
    PortfolioRecommendRequest,
    PortfolioRecommendResponse,
    PortfolioSelectRequest,
)
from app.services import portfolio as portfolio_service

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


async def _get_profile(session: AsyncSession, profile_id: int) -> UserProfile:
    profile = await session.get(UserProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다")
    return profile


@router.post("/recommend", response_model=PortfolioRecommendResponse, summary="세후 실수령액 기준 3안 추천 (STEP3)")
async def recommend_portfolios(
    body: PortfolioRecommendRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PortfolioRecommendResponse:
    profile = await _get_profile(session, body.profile_id)
    tiers = await portfolio_service.build_tiers(session, profile)
    options = [portfolio_service.to_option_out(tier_name, allocations) for tier_name, allocations in tiers.items()]
    return PortfolioRecommendResponse(options=options)


@router.post("", response_model=PortfolioOut, status_code=201, summary="추천안 확정 가입 (STEP4)")
async def select_portfolio(
    body: PortfolioSelectRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PortfolioOut:
    profile = await _get_profile(session, body.profile_id)
    tiers = await portfolio_service.build_tiers(session, profile)
    allocations = tiers.get(body.tier)
    if allocations is None:
        raise HTTPException(status_code=422, detail=f"tier 는 {list(tiers)} 중 하나여야 합니다")

    portfolio = await portfolio_service.persist_portfolio(session, profile, body.tier, allocations)
    return PortfolioOut(
        portfolio_id=portfolio.portfolio_id,
        tier=portfolio.portfolio_type,
        status=portfolio.status,
        after_tax_total=portfolio.after_tax_total,
    )


@router.get(
    "/{portfolio_id}/calendar",
    response_model=list[CalendarEventOut],
    summary="다가오는 납입·만기 일정 (STEP5)",
)
async def get_portfolio_calendar(
    portfolio_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[CalendarEventOut]:
    return await portfolio_service.get_calendar_events(session, portfolio_id)
