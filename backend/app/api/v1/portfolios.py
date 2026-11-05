"""포트폴리오 추천/선택, 만기 캘린더 API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_principal, owned_portfolio, owned_profile
from app.db.session import get_session
from app.models.user import AppUser
from app.schemas.calendar import CalendarEventOut
from app.schemas.portfolio import (
    PortfolioOut,
    PortfolioReasonsRequest,
    PortfolioReasonsResponse,
    PortfolioRecommendRequest,
    PortfolioRecommendResponse,
    PortfolioSelectRequest,
)
from app.services import portfolio as portfolio_service

router = APIRouter(prefix="/portfolios", tags=["portfolios"])

# 모두 프로필을 만든 브라우저(로그인 또는 게스트 쿠키)에서만 부를 수 있다. 남의 것이면 404
Owner = Annotated[AppUser, Depends(get_principal)]


@router.post(
    "/recommend", response_model=PortfolioRecommendResponse, summary="세후 실수령액 기준 4안 + 단일형 기준선 (STEP3)"
)
async def recommend_portfolios(
    body: PortfolioRecommendRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner: Owner,
) -> PortfolioRecommendResponse:
    profile = await owned_profile(session, body.profile_id, owner)
    plan = await portfolio_service.build_tiers(session, profile)
    options, baseline = await portfolio_service.recommend_options(session, profile, plan, with_reason=body.with_reason)
    return PortfolioRecommendResponse(options=options, baseline=baseline)


@router.post(
    "/reasons", response_model=PortfolioReasonsResponse, summary="4안의 추천 이유만 따로 (AI Summary, 약 26초)"
)
async def recommend_reasons(
    body: PortfolioReasonsRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner: Owner,
) -> PortfolioReasonsResponse:
    """결과 화면이 /recommend 를 with_reason=false 로 받아 숫자를 먼저 그린 뒤 부른다.
    같은 프로필이면 계산 결과가 같으므로 앞에서 보여준 숫자와 이유 문장 속 숫자가 어긋나지 않는다.
    AI 가 실패하면 계산값만으로 만든 기본 문구가 온다."""
    profile = await owned_profile(session, body.profile_id, owner)
    plan = await portfolio_service.build_tiers(session, profile)
    options, _ = await portfolio_service.recommend_options(session, profile, plan, with_reason=True)
    return PortfolioReasonsResponse(reasons={o.tier: o.reason for o in options if o.reason is not None})


@router.post(
    "",
    response_model=PortfolioOut,
    status_code=201,
    summary="추천안 확정 가입 (STEP4)",
    description="이미 진행중인 안이 있으면 그 안은 '완료'로 바꾸고 그만둔 시각(closed_at)을 남긴다.",
)
async def select_portfolio(
    body: PortfolioSelectRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner: Owner,
) -> PortfolioOut:
    profile = await owned_profile(session, body.profile_id, owner)
    tiers = (await portfolio_service.build_tiers(session, profile)).tiers
    allocations = tiers.get(body.tier)
    if allocations is None:
        raise HTTPException(status_code=422, detail=f"tier 는 {list(tiers)} 중 하나여야 합니다")

    await portfolio_service.close_active_portfolios(session, profile.user_id)
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
    owner: Owner,
) -> list[CalendarEventOut]:
    await owned_portfolio(session, portfolio_id, owner)
    return await portfolio_service.get_calendar_events(session, portfolio_id)
