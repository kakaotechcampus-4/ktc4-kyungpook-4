"""소셜 로그인 API.

[웹] FE 가 /auth/{provider}/login 으로 페이지 이동 → 소셜사 로그인 → /auth/{provider}/callback
→ 쿠키를 굽고 FE 로 돌려보낸다. FE 는 토큰을 직접 다루지 않는다.

[앱(안드로이드)] 쿠키 저장소가 없어 토큰을 직접 받아 Authorization 헤더로 보낸다.
  1. 앱이 PKCE verifier 를 만들고, 외부 브라우저로 /auth/{provider}/login?client=app&code_challenge=... 를 연다
  2. 소셜사 로그인 → 콜백이 APP_REDIRECT_URI(safebrother://auth)?code=<일회용 코드> 로 앱을 연다
  3. 앱이 POST /auth/app/token 에 code + code_verifier (+ guest_token) 를 보내 토큰을 JSON 으로 받는다
  토큰을 딥링크 주소에 바로 싣지 않는 건 주소가 로그·다른 앱에 새어 나갈 수 있어서다. 일회용 코드는
  60초만 유효하고, verifier 없이는 쓸 수 없다.
  로그인 전 기록은 POST /auth/app/guest 로 받은 게스트 토큰으로 쌓고, 3번에서 계정으로 옮긴다.

[평가자용] GET /auth/demo/login?secret=... 로 구글·카카오 없이 고정 데모 계정에 로그인할 수 있다.
  DEMO_LOGIN_SECRET 이 서버에 설정돼 있을 때만 동작하며 평가 기간에만 켜두는 용도다.
"""

import logging
import secrets as secrets_module
from typing import Annotated, Literal
from urllib.parse import urlencode

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
    create_guest_token,
    decode_guest_token,
    set_auth_cookies,
)
from app.db.redis import get_redis
from app.db.session import get_session
from app.models.user import AppUser
from app.schemas.auth import PKCE_CHALLENGE_PATTERN, AppTokenRequest, GuestTokenOut, RefreshRequest, TokenOut
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


def _to_app(**params: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.APP_REDIRECT_URI}?{urlencode(params)}", status_code=302)


def _app_login_failed(reason: str) -> RedirectResponse:
    return _to_app(error=reason)


async def _issue_tokens(redis: Redis, user_id: int) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user_id),
        refresh_token=await auth_service.issue_refresh(redis, user_id),
        expires_in=settings.ACCESS_TOKEN_MINUTES * 60,
    )


@router.get("/{provider}/login", summary="소셜 로그인 시작 - 소셜사 로그인 화면으로 보낸다")
async def login(
    provider: ProviderName,
    redis: Annotated[Redis, Depends(get_redis)],
    next_path: Annotated[str | None, Query(alias="next", description="로그인 후 돌아갈 FE 경로 (예: /result)")] = None,
    client: Annotated[
        Literal["web", "app"], Query(description="app 이면 끝나고 쿠키 대신 앱 딥링크로 일회용 코드를 보낸다")
    ] = "web",
    code_challenge: Annotated[
        str | None,
        Query(pattern=PKCE_CHALLENGE_PATTERN, description="client=app 필수. PKCE S256 challenge (base64url 43자)"),
    ] = None,
) -> RedirectResponse:
    if not oauth.is_configured(provider):
        raise HTTPException(status_code=503, detail=f"{provider} 로그인 키가 서버에 설정되지 않았습니다")
    if client == "app" and code_challenge is None:
        raise HTTPException(status_code=422, detail="앱 로그인은 code_challenge 가 필요합니다")
    state = await auth_service.create_state(
        redis,
        provider,
        auth_service.safe_next(next_path),
        client=client,
        code_challenge=code_challenge if client == "app" else None,
    )
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
    # state 가 없으면 웹인지 앱인지도 알 수 없어 웹 실패 화면으로 보낸다.
    login_state = await auth_service.consume_state(redis, state, provider) if state else None
    if login_state is None:
        return _login_failed("invalid_state")
    is_app = login_state.client == "app"
    failed = _app_login_failed if is_app else _login_failed
    if error or not code:  # 사용자가 소셜사 화면에서 취소함
        return failed("cancelled")

    try:
        social = await oauth.fetch_user(provider, code)
    except oauth.OAuthError:
        logger.exception("소셜 로그인 실패 (provider=%s)", provider)
        return failed("provider_error")

    user_id = await auth_service.find_or_create_user(session, social)
    if is_app:
        # 외부 브라우저에는 앱의 게스트 토큰이 없다. 게스트 승계는 앱이 /auth/app/token 에서 토큰을 줄 때 한다
        app_code = await auth_service.create_app_code(redis, user_id, login_state.code_challenge)
        return _to_app(code=app_code)

    response = _to_frontend(login_state.next_path)
    set_auth_cookies(response, create_access_token(user_id), await auth_service.issue_refresh(redis, user_id))
    # 로그인 전에 게스트로 만든 기록은 이 계정으로 옮긴다
    guest_id = decode_guest_token(guest_token) if guest_token else None
    if guest_id is not None:
        await auth_service.adopt_guest(session, guest_id, user_id)
        clear_guest_cookie(response)
    return response


@router.get(
    "/demo/login",
    summary="[평가자용] 소셜 로그인 없이 체험 - secret 쿼리파라미터 필요",
    description="DEMO_LOGIN_SECRET 이 서버에 설정돼 있고 secret 이 일치할 때만 동작한다 "
    "(비어 있으면 항상 404, 기본 비활성). 고정된 데모 계정으로 로그인시키고(웹 쿠키), "
    "게스트로 쌓아둔 기록이 있으면 그 계정으로 그대로 승계한다.",
    responses={404: {"description": "DEMO_LOGIN_SECRET 미설정 또는 secret 불일치"}},
)
async def demo_login(
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    secret: str,
    next_path: Annotated[str | None, Query(alias="next", description="로그인 후 돌아갈 FE 경로")] = None,
    guest_token: Annotated[str | None, Cookie(alias=GUEST_COOKIE)] = None,
) -> RedirectResponse:
    if not settings.DEMO_LOGIN_SECRET or not secrets_module.compare_digest(secret, settings.DEMO_LOGIN_SECRET):
        raise HTTPException(status_code=404)

    user_id = await auth_service.find_or_create_demo_user(session)
    response = _to_frontend(auth_service.safe_next(next_path))
    set_auth_cookies(response, create_access_token(user_id), await auth_service.issue_refresh(redis, user_id))
    guest_id = decode_guest_token(guest_token) if guest_token else None
    if guest_id is not None:
        await auth_service.adopt_guest(session, guest_id, user_id)
        clear_guest_cookie(response)
    return response


@router.post(
    "/app/guest",
    response_model=GuestTokenOut,
    status_code=201,
    summary="[앱] 게스트 토큰 발급 - 로그인 전 기록의 주인",
    description="앱을 처음 켜서 프로필을 만들기 전에 한 번 부른다. 받은 토큰을 기기에 저장하고 "
    "`Authorization: Bearer <guest_token>` 으로 보내면 웹의 게스트 쿠키와 똑같이 동작한다 (30일 유효).",
)
async def issue_app_guest(session: Annotated[AsyncSession, Depends(get_session)]) -> GuestTokenOut:
    guest = AppUser(nickname="guest")
    session.add(guest)
    await session.commit()
    return GuestTokenOut(guest_token=create_guest_token(guest.user_id))


@router.post(
    "/app/token",
    response_model=TokenOut,
    summary="[앱] 일회용 코드를 토큰으로 교환 + 게스트 기록 승계",
    responses={400: {"description": "코드가 없거나·만료됐거나(60초)·이미 썼거나·verifier 가 틀림 → 로그인부터 다시"}},
)
async def exchange_app_code(
    body: AppTokenRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> TokenOut:
    user_id = await auth_service.consume_app_code(redis, body.code, body.code_verifier)
    if user_id is None:
        raise HTTPException(status_code=400, detail="로그인을 다시 시도해 주세요")
    # 로그인 전에 게스트로 만든 기록은 이 계정으로 옮긴다 (웹의 콜백과 같은 처리)
    guest_id = decode_guest_token(body.guest_token) if body.guest_token else None
    if guest_id is not None:
        await auth_service.adopt_guest(session, guest_id, user_id)
    return await _issue_tokens(redis, user_id)


@router.post(
    "/refresh",
    status_code=204,
    summary="access 토큰 재발급 - 401 을 받으면 한 번 호출",
    description="웹은 refresh 쿠키로 부르고 204 + 새 쿠키를 받는다. "
    "앱은 본문에 refresh_token 을 넣어 부르고 200 + 새 토큰(JSON)을 받는다.",
    responses={
        200: {"model": TokenOut, "description": "앱 - 새 access/refresh 토큰"},
        401: {"description": "refresh 토큰이 없거나 만료됨 → 다시 로그인"},
    },
)
async def refresh(
    redis: Annotated[Redis, Depends(get_redis)],
    body: RefreshRequest | None = None,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> Response:
    if refresh_token is None and body is not None:  # 앱
        rotated = await auth_service.rotate_refresh(redis, body.refresh_token)
        if rotated is None:
            raise HTTPException(status_code=401, detail="다시 로그인해 주세요")
        user_id, new_refresh = rotated
        tokens = TokenOut(
            access_token=create_access_token(user_id),
            refresh_token=new_refresh,
            expires_in=settings.ACCESS_TOKEN_MINUTES * 60,
        )
        return JSONResponse(tokens.model_dump())

    rotated = await auth_service.rotate_refresh(redis, refresh_token) if refresh_token else None
    if rotated is None:
        # 쿠키는 지우지 않는다. 늦게 도착한 옛 요청의 실패가 이미 받은 새 refresh 쿠키까지 지우면 로그아웃된다.
        # 로그아웃은 /auth/logout 에서만 한다
        return JSONResponse(status_code=401, content={"detail": "다시 로그인해 주세요"})

    user_id, new_refresh = rotated
    response = Response(status_code=204)
    set_auth_cookies(response, create_access_token(user_id), new_refresh)
    return response


@router.post("/logout", status_code=204, summary="로그아웃 (앱은 본문에 refresh_token 을 넣는다)")
async def logout(
    redis: Annotated[Redis, Depends(get_redis)],
    body: RefreshRequest | None = None,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> Response:
    token = refresh_token or (body.refresh_token if body else None)
    if token:
        await auth_service.revoke_refresh(redis, token)
    response = Response(status_code=204)
    clear_auth_cookies(response)
    return response
