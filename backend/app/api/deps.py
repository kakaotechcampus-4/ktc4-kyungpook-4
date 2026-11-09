"""여러 라우터가 같이 쓰는 FastAPI 의존성."""

from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ACCESS_COOKIE, GUEST_COOKIE, decode_access_token, decode_guest_token
from app.db.session import get_session
from app.models.portfolio import UserPortfolio
from app.models.profile import UserProfile
from app.models.user import AppUser


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str | None:
    """앱(안드로이드)은 쿠키 저장소가 없어 토큰을 `Authorization: Bearer <토큰>` 헤더로 보낸다.
    웹은 지금처럼 쿠키만 쓴다. 헤더에는 access 토큰이나 guest 토큰이 올 수 있고, 종류(typ)로 구분한다."""
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return token.strip() or None


async def get_current_user_optional(
    session: Annotated[AsyncSession, Depends(get_session)],
    bearer: Annotated[str | None, Depends(bearer_token)],
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
) -> AppUser | None:
    """로그인했으면 그 사용자, 아니면 None. 토큰이 만료됐거나 위조됐어도 None 이다."""
    for token in (bearer, access_token):
        user_id = decode_access_token(token) if token else None
        if user_id is not None:
            return await session.get(AppUser, user_id)  # 탈퇴 등으로 계정이 없으면 None
    return None


async def get_current_user(user: Annotated[AppUser | None, Depends(get_current_user_optional)]) -> AppUser:
    """로그인 필수. FE 는 401 을 받으면 /auth/refresh 를 한 번 시도한다."""
    if user is None:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    return user


async def get_principal_optional(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[AppUser | None, Depends(get_current_user_optional)],
    bearer: Annotated[str | None, Depends(bearer_token)],
    guest_token: Annotated[str | None, Cookie(alias=GUEST_COOKIE)] = None,
) -> AppUser | None:
    """로그인한 사용자, 아니면 게스트 토큰(헤더 또는 쿠키)의 익명 사용자, 둘 다 없으면 None.

    프로필·포트폴리오처럼 로그인 전에도 쓰는 기록의 주인을 가릴 때 쓴다.
    """
    if user is not None:
        return user
    for token in (bearer, guest_token):
        guest_id = decode_guest_token(token) if token else None
        if guest_id is not None:
            return await session.get(AppUser, guest_id)  # 로그인으로 이관돼 지워졌으면 None
    return None


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
