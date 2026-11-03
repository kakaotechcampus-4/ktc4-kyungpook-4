"""소셜 로그인 API 흐름 (app/api/v1/auth.py, users.py).

소셜사 호출(oauth.fetch_user)만 가짜로 바꾸고, DB 는 테스트 DB 를, Redis 는 fakeredis 를 쓴다.
DB 가 안 떠 있으면 conftest 가 skip 한다.
"""

import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401  - Base.metadata 를 채운다
from app.core.config import settings
from app.db.base import Base
from app.db.redis import get_redis
from app.db.session import get_session
from app.main import app
from app.services import oauth
from app.services.oauth import OAuthError, SocialUser

FRONT = "http://front"


@pytest.fixture(scope="module")
def async_db_url(test_database_url):
    eng = create_engine(test_database_url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(eng)
    eng.dispose()
    return test_database_url.replace("postgresql+psycopg2", "postgresql+asyncpg")


@pytest.fixture(autouse=True)
def auth_settings(monkeypatch):
    # 로컬 .env 의 실제 키가 테스트에 섞이지 않게 전부 덮어쓴다
    monkeypatch.setattr(settings, "JWT_SECRET", "api-test-secret-" + "x" * 32)
    monkeypatch.setattr(settings, "ENV", "local")
    monkeypatch.setattr(settings, "BACKEND_PUBLIC_URL", "http://testserver")
    monkeypatch.setattr(settings, "FRONTEND_URL", FRONT)
    for name in ("GOOGLE", "KAKAO", "NAVER"):
        monkeypatch.setattr(settings, f"{name}_CLIENT_ID", f"{name.lower()}-id")
        monkeypatch.setattr(settings, f"{name}_CLIENT_SECRET", f"{name.lower()}-secret")


@pytest.fixture
async def client(async_db_url):
    engine = create_async_engine(async_db_url)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    fake_redis = FakeAsyncRedis(decode_responses=True)

    async def _session():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_redis] = lambda: fake_redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


def fake_provider(monkeypatch, result: SocialUser | Exception) -> None:
    async def _fetch_user(provider, code, state):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(oauth, "fetch_user", _fetch_user)


def social(provider: str = "KAKAO", email: str | None = None, nickname: str | None = "덕환") -> SocialUser:
    return SocialUser(provider, uuid.uuid4().hex, email, nickname)  # 테스트끼리 계정이 겹치지 않게


async def start_login(client: AsyncClient, provider: str = "kakao", next_path: str | None = "/result") -> str:
    """login 을 호출하고 소셜사로 보낸 주소에서 state 를 꺼낸다."""
    params = {"next": next_path} if next_path is not None else {}
    res = await client.get(f"/api/v1/auth/{provider}/login", params=params)
    assert res.status_code == 302
    return parse_qs(urlparse(res.headers["location"]).query)["state"][0]


async def login(client: AsyncClient, provider: str = "kakao", next_path: str | None = "/result"):
    state = await start_login(client, provider, next_path)
    return await client.get(f"/api/v1/auth/{provider}/callback", params={"code": "auth-code", "state": state})


async def me(client: AsyncClient):
    return await client.get("/api/v1/users/me")


# ── 로그인 ────────────────────────────────────────────────────


async def test_login_redirects_to_provider_with_registered_redirect_uri(client):
    res = await client.get("/api/v1/auth/google/login")
    url = urlparse(res.headers["location"])
    query = parse_qs(url.query)
    assert f"{url.scheme}://{url.netloc}{url.path}" == "https://accounts.google.com/o/oauth2/v2/auth"
    assert query["client_id"] == ["google-id"]
    assert query["redirect_uri"] == ["http://testserver/api/v1/auth/google/callback"]
    assert query["scope"] == ["openid email profile"]


async def test_first_login_creates_user_and_sets_cookies(client, monkeypatch):
    fake_provider(monkeypatch, social("KAKAO", nickname="덕환"))
    res = await login(client)

    assert res.headers["location"] == f"{FRONT}/#/result"
    assert client.cookies.get("access_token")
    assert client.cookies.get("refresh_token")
    body = (await me(client)).json()
    assert body["nickname"] == "덕환"
    assert body["providers"] == ["KAKAO"]
    assert body["is_guest"] is False


async def test_cookies_are_httponly_and_lax(client, monkeypatch):
    fake_provider(monkeypatch, social())
    res = await login(client)
    cookies = res.headers.get_list("set-cookie")
    assert len(cookies) == 2
    for cookie in cookies:
        assert "HttpOnly" in cookie
        assert "SameSite=lax" in cookie


async def test_relogin_with_same_account_is_same_user(client, monkeypatch):
    account = social("NAVER")
    fake_provider(monkeypatch, account)
    await login(client, "naver")
    first = (await me(client)).json()["user_id"]

    client.cookies.clear()
    await login(client, "naver")
    assert (await me(client)).json()["user_id"] == first


async def test_same_email_on_other_provider_is_not_merged(client, monkeypatch):
    fake_provider(monkeypatch, social("GOOGLE", email="same@example.com"))
    await login(client, "google")
    google_user = (await me(client)).json()["user_id"]

    client.cookies.clear()
    fake_provider(monkeypatch, social("NAVER", email="same@example.com"))
    await login(client, "naver")
    assert (await me(client)).json()["user_id"] != google_user


async def test_missing_nickname_gets_default(client, monkeypatch):
    fake_provider(monkeypatch, social(nickname=None))
    await login(client)
    assert (await me(client)).json()["nickname"] == "사용자"


@pytest.mark.parametrize("next_path", ["//evil.com", "https://evil.com", None])
async def test_unsafe_or_missing_next_goes_home(client, monkeypatch, next_path):
    fake_provider(monkeypatch, social())
    res = await login(client, next_path=next_path)
    assert res.headers["location"] == f"{FRONT}/#/"


# ── 로그인 실패 ──────────────────────────────────────────────


async def test_unknown_state_is_rejected(client, monkeypatch):
    fake_provider(monkeypatch, social())
    res = await client.get("/api/v1/auth/kakao/callback", params={"code": "c", "state": "forged"})
    assert res.headers["location"] == f"{FRONT}/#/login?error=invalid_state"
    assert "access_token" not in client.cookies


async def test_state_cannot_be_reused(client, monkeypatch):
    fake_provider(monkeypatch, social())
    state = await start_login(client)
    params = {"code": "c", "state": state}
    await client.get("/api/v1/auth/kakao/callback", params=params)
    client.cookies.clear()

    res = await client.get("/api/v1/auth/kakao/callback", params=params)
    assert res.headers["location"] == f"{FRONT}/#/login?error=invalid_state"


async def test_state_is_bound_to_provider(client, monkeypatch):
    fake_provider(monkeypatch, social())
    state = await start_login(client, "kakao")
    res = await client.get("/api/v1/auth/naver/callback", params={"code": "c", "state": state})
    assert res.headers["location"] == f"{FRONT}/#/login?error=invalid_state"


async def test_user_cancelled_on_provider(client, monkeypatch):
    fake_provider(monkeypatch, social())
    state = await start_login(client)
    res = await client.get("/api/v1/auth/kakao/callback", params={"error": "access_denied", "state": state})
    assert res.headers["location"] == f"{FRONT}/#/login?error=cancelled"


async def test_provider_failure(client, monkeypatch):
    fake_provider(monkeypatch, OAuthError("token exchange failed"))
    res = await login(client)
    assert res.headers["location"] == f"{FRONT}/#/login?error=provider_error"
    assert "access_token" not in client.cookies


async def test_unconfigured_provider_returns_503(client, monkeypatch):
    monkeypatch.setattr(settings, "NAVER_CLIENT_SECRET", "")
    res = await client.get("/api/v1/auth/naver/login")
    assert res.status_code == 503


async def test_unknown_provider_returns_422(client):
    res = await client.get("/api/v1/auth/facebook/login")
    assert res.status_code == 422


# ── refresh / logout / me ───────────────────────────────────


async def test_me_requires_login(client):
    assert (await me(client)).status_code == 401
    client.cookies.set("access_token", "garbage")
    assert (await me(client)).status_code == 401


async def test_refresh_rotates_and_old_token_is_dead(client, monkeypatch):
    fake_provider(monkeypatch, social())
    await login(client)
    old_refresh = client.cookies.get("refresh_token")

    res = await client.post("/api/v1/auth/refresh")
    assert res.status_code == 204
    new_refresh = client.cookies.get("refresh_token")
    assert new_refresh and new_refresh != old_refresh
    assert (await me(client)).status_code == 200

    # 이미 쓴 refresh 토큰을 다시 내면 거부하고 쿠키도 지운다
    client.cookies.clear()
    res = await client.post("/api/v1/auth/refresh", headers={"Cookie": f"refresh_token={old_refresh}"})
    assert res.status_code == 401


async def test_refresh_without_cookie_is_401(client):
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_logout_revokes_refresh_and_clears_cookies(client, monkeypatch):
    fake_provider(monkeypatch, social())
    await login(client)
    refresh_token = client.cookies.get("refresh_token")

    res = await client.post("/api/v1/auth/logout")
    assert res.status_code == 204
    assert "access_token" not in client.cookies
    assert "refresh_token" not in client.cookies
    assert (await me(client)).status_code == 401

    res = await client.post("/api/v1/auth/refresh", headers={"Cookie": f"refresh_token={refresh_token}"})
    assert res.status_code == 401
