"""사용자 API."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import AppUser, SocialAccount
from app.schemas.user import UserMeOut

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
