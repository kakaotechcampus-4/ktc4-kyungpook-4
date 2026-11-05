"""여러 라우터가 같이 쓰는 FastAPI 의존성."""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ACCESS_COOKIE, GUEST_COOKIE, decode_access_token, decode_guest_token
from app.db.session import get_session
from app.models.portfolio import UserPortfolio
from app.models.profile import UserProfile
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


async def get_principal_optional(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[AppUser | None, Depends(get_current_user_optional)],
    guest_token: Annotated[str | None, Cookie(alias=GUEST_COOKIE)] = None,
) -> AppUser | None:
    """로그인한 사용자, 아니면 게스트 쿠키의 익명 사용자, 둘 다 없으면 None.

    프로필·포트폴리오처럼 로그인 전에도 쓰는 기록의 주인을 가릴 때 쓴다.
    """
    if user is not None:
        return user
    if guest_token is None:
        return None
    guest_id = decode_guest_token(guest_token)
    if guest_id is None:
        return None
    return await session.get(AppUser, guest_id)  # 로그인으로 이관돼 지워졌으면 None


async def get_principal(user: Annotated[AppUser | None, Depends(get_principal_optional)]) -> AppUser:
    """로그인 또는 게스트 쿠키 필수. 둘 다 없으면 이 브라우저가 만든 기록이 아니다."""
    if user is None:
        raise HTTPException(status_code=401, detail="이 브라우저에서 만든 기록이 아니거나 세션이 만료됐습니다")
    return user


async def owned_profile(session: AsyncSession, profile_id: int, owner: AppUser) -> UserProfile:
    """남의 프로필이면 있다는 것도 알리지 않고 404."""
    profile = await session.get(UserProfile, profile_id)
    if profile is None or profile.user_id != owner.user_id:
        raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다")
    return profile


async def owned_portfolio(session: AsyncSession, portfolio_id: int, owner: AppUser) -> UserPortfolio:
    portfolio = await session.get(UserPortfolio, portfolio_id)
    if portfolio is None or portfolio.user_id != owner.user_id:
        raise HTTPException(status_code=404, detail="포트폴리오를 찾을 수 없습니다")
    return portfolio
