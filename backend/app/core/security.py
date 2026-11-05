"""로그인 토큰 발급·검증과 인증 쿠키.

access 토큰은 JWT 라 서버에 저장하지 않고 서명만 확인한다.
refresh 토큰은 그냥 랜덤 문자열이고, 유효한지는 Redis 에 있는지로 판단한다 (services/auth.py).
guest 토큰은 로그인 안 한 사용자가 자기 프로필·포트폴리오를 다시 찾아오기 위한 JWT 다.
모두 HttpOnly 쿠키로만 오가므로 FE 코드는 토큰 값을 볼 수 없다.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Response

from app.core.config import settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
GUEST_COOKIE = "guest_token"
_ALGORITHM = "HS256"
# 게스트는 refresh 가 없어 길게 둔다. 로그인하면 이 게스트의 기록을 그 계정으로 옮기고 지운다
GUEST_TOKEN_DAYS = 30

# access 는 모든 API 에 실려야 하고, refresh 는 /auth 아래에서만 실리면 된다 (노출 범위를 줄인다)
_ACCESS_PATH = "/api"
_REFRESH_PATH = f"{settings.API_V1_PREFIX}/auth"


def _encode(user_id: int, typ: str, lifetime: timedelta) -> str:
    if not settings.JWT_SECRET:
        raise RuntimeError("JWT_SECRET 이 비어 있어 토큰을 발급할 수 없다")
    now = datetime.now(UTC)
    payload = {"sub": str(user_id), "typ": typ, "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=_ALGORITHM)


def _decode(token: str, typ: str) -> int | None:
    """유효하면 user_id, 만료·위조·형식 오류·종류가 다르면 None."""
    if not settings.JWT_SECRET:
        return None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[_ALGORITHM], options={"require": ["sub", "exp"]})
    except jwt.InvalidTokenError:
        return None
    # typ 이 생기기 전에 발급한 access 토큰에는 typ 이 없다
    if payload.get("typ", "access") != typ:
        return None
    try:
        return int(payload["sub"])
    except ValueError:
        return None


def create_access_token(user_id: int) -> str:
    return _encode(user_id, "access", timedelta(minutes=settings.ACCESS_TOKEN_MINUTES))


def decode_access_token(token: str) -> int | None:
    return _decode(token, "access")


def create_guest_token(user_id: int) -> str:
    return _encode(user_id, "guest", timedelta(days=GUEST_TOKEN_DAYS))


def decode_guest_token(token: str) -> int | None:
    return _decode(token, "guest")


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Redis 키에는 원문 대신 해시를 쓴다. Redis 내용이 새도 그대로 쓸 수 없게."""
    return hashlib.sha256(token.encode()).hexdigest()


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    # SameSite 는 Lax 여야 한다. Strict 면 소셜사에서 콜백으로 돌아오는 요청에 쿠키가 안 실린다.
    common = {"httponly": True, "secure": settings.cookie_secure, "samesite": "lax"}
    response.set_cookie(
        ACCESS_COOKIE, access_token, max_age=settings.ACCESS_TOKEN_MINUTES * 60, path=_ACCESS_PATH, **common
    )
    response.set_cookie(
        REFRESH_COOKIE, refresh_token, max_age=settings.REFRESH_TOKEN_DAYS * 86400, path=_REFRESH_PATH, **common
    )


def clear_auth_cookies(response: Response) -> None:
    common = {"httponly": True, "secure": settings.cookie_secure, "samesite": "lax"}
    response.delete_cookie(ACCESS_COOKIE, path=_ACCESS_PATH, **common)
    response.delete_cookie(REFRESH_COOKIE, path=_REFRESH_PATH, **common)


def set_guest_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        GUEST_COOKIE,
        create_guest_token(user_id),
        max_age=GUEST_TOKEN_DAYS * 86400,
        path=_ACCESS_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def clear_guest_cookie(response: Response) -> None:
    response.delete_cookie(
        GUEST_COOKIE, path=_ACCESS_PATH, httponly=True, secure=settings.cookie_secure, samesite="lax"
    )
