"""사용자 API."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_principal
from app.db.session import get_session
from app.models.user import AppUser, SocialAccount
from app.schemas.user import RoadmapOut, UserMeOut
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
        is_guest=not providers,
        providers=providers,
    )


@router.get(
    "/me/roadmap",
    response_model=RoadmapOut,
    summary="로드맵 숫자 - 경과 개월, 총 이자, 현재 이자 (세후)",
    description="로그인 또는 게스트 쿠키 필요. 이자는 가입 때 확정금리로 오늘까지 쌓인 만큼을 단리로 센다.",
    responses={401: {"description": "로그인도 게스트 쿠키도 없음"}},
)
async def get_my_roadmap(
    user: Annotated[AppUser, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RoadmapOut:
    numbers = await build_roadmap(session, user, date.today())
    return RoadmapOut(**numbers.__dict__)
