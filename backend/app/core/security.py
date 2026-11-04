"""로그인 토큰 발급·검증과 인증 쿠키.

access 토큰은 JWT 라 서버에 저장하지 않고 서명만 확인한다.
refresh 토큰은 그냥 랜덤 문자열이고, 유효한지는 Redis 에 있는지로 판단한다 (services/auth.py).
둘 다 HttpOnly 쿠키로만 오가므로 FE 코드는 토큰 값을 볼 수 없다.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Response

from app.core.config import settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
_ALGORITHM = "HS256"

# access 는 모든 API 에 실려야 하고, refresh 는 /auth 아래에서만 실리면 된다 (노출 범위를 줄인다)
_ACCESS_PATH = "/api"
_REFRESH_PATH = f"{settings.API_V1_PREFIX}/auth"


def create_access_token(user_id: int) -> str:
    if not settings.JWT_SECRET:
        raise RuntimeError("JWT_SECRET 이 비어 있어 토큰을 발급할 수 없다")
    now = datetime.now(UTC)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """유효하면 user_id, 만료·위조·형식 오류면 None."""
    if not settings.JWT_SECRET:
        return None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[_ALGORITHM], options={"require": ["sub", "exp"]})
        return int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None


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
