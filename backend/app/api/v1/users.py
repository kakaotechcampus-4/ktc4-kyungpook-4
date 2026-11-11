"""사용자 API."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_principal
from app.core import clock
from app.db.session import get_session
from app.models.user import AppUser, SocialAccount
from app.schemas.calendar import CalendarEventOut
from app.schemas.user import RoadmapOut, UserMeOut
from app.services import auth as auth_service
from app.services import portfolio as portfolio_service
from app.services.roadmap import build_roadmap

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserMeOut,
    summary="현재 로그인한 사용자 - FE 가 로그인 여부를 확인할 때 쓴다",
    responses={401: {"description": "로그인 안 됨 (또는 access 토큰 만료 → /auth/refresh)"}},
)
async def get_me(
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserMeOut:
    providers = list(
        (
            await session.execute(
                select(SocialAccount.provider)
                .where(SocialAccount.user_id == user.user_id)
                .order_by(SocialAccount.linked_at)
            )
        ).scalars()
    )
    return UserMeOut(
        user_id=user.user_id,
        nickname=user.nickname,
        email=user.email,
        # 데모 계정은 소셜 계정이 없지만 로그인한 사용자다
        is_guest=not providers and user.email != auth_service.DEMO_USER_EMAIL,
        providers=providers,
    )


@router.get(
    "/me/roadmap",
    response_model=RoadmapOut,
    summary="로드맵 숫자 - 경과 개월, 총 이자, 현재 이자 (세후)",
    description="로그인 또는 게스트 쿠키 필요. 이자는 가입 때 확정금리로 오늘(한국 시간)까지 쌓인 만큼을 단리로 센다. "
    "목표 경로의 현재 위치는 active_total, 목표는 goal_amount 를 쓴다.",
    responses={401: {"description": "로그인도 게스트 쿠키도 없음"}},
)
async def get_my_roadmap(
    user: Annotated[AppUser, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RoadmapOut:
    numbers = await build_roadmap(session, user, clock.today())
    return RoadmapOut(**numbers.__dict__)


@router.get(
    "/me/calendar",
    response_model=list[CalendarEventOut],
    summary="내 진행중 안의 다가오는 납입·만기 일정",
    description="포트폴리오 번호 없이 지금 사용자(로그인 또는 게스트 쿠키)의 진행중 안을 찾아 일정을 준다. "
    "같은 계정으로 로그인하면 다른 브라우저·새로고침 뒤에도 같은 일정이 나온다. 진행중 안이 없으면 빈 목록.",
    responses={401: {"description": "로그인도 게스트 쿠키도 없음"}},
)
async def get_my_calendar(
    user: Annotated[AppUser, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[CalendarEventOut]:
    portfolio_id = await portfolio_service.active_portfolio_id(session, user.user_id)
    if portfolio_id is None:
        return []
    return await portfolio_service.get_calendar_events(session, portfolio_id)
