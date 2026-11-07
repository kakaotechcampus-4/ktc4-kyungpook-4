"""소셜 로그인 API.

흐름: FE 가 /auth/{provider}/login 으로 페이지 이동 → 소셜사 로그인 → /auth/{provider}/callback
→ 쿠키를 굽고 FE 로 돌려보낸다. FE 는 토큰을 직접 다루지 않는다.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse, RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    GUEST_COOKIE,
    REFRESH_COOKIE,
    clear_auth_cookies,
    clear_guest_cookie,
    create_access_token,
    decode_guest_token,
    set_access_cookie,
    set_auth_cookies,
)
from app.db.redis import get_redis
from app.db.session import get_session
from app.services import auth as auth_service
from app.services import oauth
from app.services.oauth import ProviderName

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_frontend(path: str) -> RedirectResponse:
    # FE 는 go_router 해시 전략이라 경로가 # 뒤에 온다 (https://.../#/result)
    return RedirectResponse(f"{settings.FRONTEND_URL}/#{path}", status_code=302)


def _login_failed(reason: str) -> RedirectResponse:
    return _to_frontend(f"/login?error={reason}")


@router.get("/{provider}/login", summary="소셜 로그인 시작 - 소셜사 로그인 화면으로 보낸다")
async def login(
    provider: ProviderName,
    redis: Annotated[Redis, Depends(get_redis)],
    next_path: Annotated[str | None, Query(alias="next", description="로그인 후 돌아갈 FE 경로 (예: /result)")] = None,
) -> RedirectResponse:
    if not oauth.is_configured(provider):
        raise HTTPException(status_code=503, detail=f"{provider} 로그인 키가 서버에 설정되지 않았습니다")
    state = await auth_service.create_state(redis, provider, auth_service.safe_next(next_path))
    return RedirectResponse(oauth.authorize_url(provider, state), status_code=302)


@router.get("/{provider}/callback", summary="소셜사가 돌려보내는 곳 - 쿠키를 굽고 FE 로 보낸다")
async def callback(
    provider: ProviderName,
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    guest_token: Annotated[str | None, Cookie(alias=GUEST_COOKIE)] = None,
) -> RedirectResponse:
    # state 를 먼저 확인한다. 우리가 시작하지 않은 로그인(CSRF)이면 여기서 끊긴다.
    next_path = await auth_service.consume_state(redis, state, provider) if state else None
    if next_path is None:
        return _login_failed("invalid_state")
    if error or not code:  # 사용자가 소셜사 화면에서 취소함
        return _login_failed("cancelled")

    try:
        social = await oauth.fetch_user(provider, code)
    except oauth.OAuthError:
        logger.exception("소셜 로그인 실패 (provider=%s)", provider)
        return _login_failed("provider_error")

    user_id = await auth_service.find_or_create_user(session, social)
    response = _to_frontend(next_path)
    set_auth_cookies(response, create_access_token(user_id), await auth_service.issue_refresh(redis, user_id))
    # 로그인 전에 게스트로 만든 기록은 이 계정으로 옮긴다
    guest_id = decode_guest_token(guest_token) if guest_token else None
    if guest_id is not None:
        await auth_service.adopt_guest(session, guest_id, user_id)
        clear_guest_cookie(response)
    return response


@router.post(
    "/refresh",
    status_code=204,
    summary="access 토큰 재발급 - 401 을 받으면 한 번 호출",
    responses={401: {"description": "refresh 토큰이 없거나 만료됨 → 다시 로그인"}},
)
async def refresh(
    redis: Annotated[Redis, Depends(get_redis)],
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> Response:
    rotated = await auth_service.rotate_refresh(redis, refresh_token) if refresh_token else None
    if rotated is None:
        # 쿠키는 지우지 않는다. 늦게 도착한 옛 요청의 실패가 이미 받은 새 refresh 쿠키까지 지우면 로그아웃된다.
        # 로그아웃은 /auth/logout 에서만 한다
        return JSONResponse(status_code=401, content={"detail": "다시 로그인해 주세요"})

    user_id, new_refresh = rotated
    response = Response(status_code=204)
    if new_refresh is None:  # 다른 요청이 이미 교체함 - access 만 새로 준다
        set_access_cookie(response, create_access_token(user_id))
    else:
        set_auth_cookies(response, create_access_token(user_id), new_refresh)
    return response


@router.post("/logout", status_code=204, summary="로그아웃")
async def logout(
    redis: Annotated[Redis, Depends(get_redis)],
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> Response:
    if refresh_token:
        await auth_service.revoke_refresh(redis, refresh_token)
    response = Response(status_code=204)
    clear_auth_cookies(response)
    return response
