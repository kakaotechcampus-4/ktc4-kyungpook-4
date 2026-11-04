"""소셜사(구글·카카오) OAuth 차이를 여기서 흡수한다.

밖에서는 is_configured / authorize_url / fetch_user 만 쓴다.
소셜사별 주소·파라미터·응답 모양은 이 파일 밖으로 새지 않게 한다.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlencode

import httpx

from app.core.config import settings

ProviderName = Literal["google", "kakao"]  # URL 경로에 쓰는 이름

_TIMEOUT = httpx.Timeout(5.0)


@dataclass(frozen=True)
class SocialUser:
    provider: str  # DB 값 (enums.SOCIAL_PROVIDERS)
    provider_user_id: str
    email: str | None
    nickname: str | None


class OAuthError(Exception):
    """소셜사 호출이 실패했거나 응답이 기대한 모양이 아니다."""


def _parse_google(data: dict[str, Any]) -> SocialUser:
    return SocialUser("GOOGLE", str(data["sub"]), data.get("email"), data.get("name"))


def _parse_kakao(data: dict[str, Any]) -> SocialUser:
    # 이메일은 비즈 앱만 받을 수 있어서 대부분 없다
    account = data.get("kakao_account") or {}
    profile = account.get("profile") or {}
    return SocialUser("KAKAO", str(data["id"]), account.get("email"), profile.get("nickname"))


@dataclass(frozen=True)
class _Provider:
    authorize_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    client_id_key: str  # settings 속성 이름. 테스트에서 값을 바꿔 끼울 수 있게 매번 읽는다
    client_secret_key: str
    parse: Callable[[dict[str, Any]], SocialUser]
    scope: str | None = None  # 카카오는 받을 항목을 콘솔의 동의항목으로 정한다


_PROVIDERS: dict[str, _Provider] = {
    "google": _Provider(
        authorize_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
        token_endpoint="https://oauth2.googleapis.com/token",
        userinfo_endpoint="https://openidconnect.googleapis.com/v1/userinfo",
        client_id_key="GOOGLE_CLIENT_ID",
        client_secret_key="GOOGLE_CLIENT_SECRET",
        parse=_parse_google,
        scope="openid email profile",
    ),
    "kakao": _Provider(
        authorize_endpoint="https://kauth.kakao.com/oauth/authorize",
        token_endpoint="https://kauth.kakao.com/oauth/token",
        userinfo_endpoint="https://kapi.kakao.com/v2/user/me",
        client_id_key="KAKAO_CLIENT_ID",
        client_secret_key="KAKAO_CLIENT_SECRET",
        parse=_parse_kakao,
    ),
}


def _credentials(provider: str) -> tuple[str, str]:
    p = _PROVIDERS[provider]
    return getattr(settings, p.client_id_key), getattr(settings, p.client_secret_key)


def redirect_uri(provider: str) -> str:
    return f"{settings.BACKEND_PUBLIC_URL}{settings.API_V1_PREFIX}/auth/{provider}/callback"


def is_configured(provider: str) -> bool:
    client_id, client_secret = _credentials(provider)
    return bool(client_id and client_secret)


def authorize_url(provider: str, state: str) -> str:
    p = _PROVIDERS[provider]
    client_id, _ = _credentials(provider)
    params = {"response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri(provider), "state": state}
    if p.scope:
        params["scope"] = p.scope
    return f"{p.authorize_endpoint}?{urlencode(params)}"


async def fetch_user(provider: str, code: str) -> SocialUser:
    """인가 코드를 소셜사 토큰으로 바꾸고, 그 토큰으로 사용자 정보를 받아온다."""
    p = _PROVIDERS[provider]
    client_id, client_secret = _credentials(provider)
    form = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri(provider),
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            token_res = await client.post(p.token_endpoint, data=form)
            access_token = token_res.json().get("access_token")
            if token_res.status_code != 200 or not access_token:
                raise OAuthError(f"{provider} token exchange failed: {token_res.status_code} {token_res.text[:200]}")

            user_res = await client.get(p.userinfo_endpoint, headers={"Authorization": f"Bearer {access_token}"})
            if user_res.status_code != 200:
                raise OAuthError(f"{provider} userinfo failed: {user_res.status_code} {user_res.text[:200]}")
            return p.parse(user_res.json())
    except (httpx.HTTPError, ValueError, KeyError) as exc:  # 네트워크 오류, JSON 아님, 필드 없음
        raise OAuthError(f"{provider}: {exc!r}") from exc
