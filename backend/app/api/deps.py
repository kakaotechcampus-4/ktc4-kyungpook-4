"""여러 라우터가 같이 쓰는 FastAPI 의존성."""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ACCESS_COOKIE, decode_access_token
from app.db.session import get_session
from app.models.user import AppUser


async def get_current_user_optional(
    session: Annotated[AsyncSession, Depends(get_session)],
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
) -> AppUser | None:
    """로그인했으면 그 사용자, 아니면 None. 토큰이 만료됐거나 위조됐어도 None 이다."""
    if access_token is None:
        return None
    user_id = decode_access_token(access_token)
    if user_id is None:
        return None
    return await session.get(AppUser, user_id)  # 탈퇴 등으로 계정이 없으면 None


async def get_current_user(user: Annotated[AppUser | None, Depends(get_current_user_optional)]) -> AppUser:
    """로그인 필수. FE 는 401 을 받으면 /auth/refresh 를 한 번 시도한다."""
    if user is None:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    return user
