"""앱(안드로이드) 로그인·게스트 - 쿠키 대신 Authorization 헤더와 JSON 토큰으로 동작하는지.

소셜사 호출(oauth.fetch_user)만 가짜로 바꾸고, DB 는 테스트 DB 를, Redis 는 fakeredis 를 쓴다.
DB 가 안 떠 있으면 conftest 가 skip 한다.
"""

import secrets
import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401  - Base.metadata 를 채운다
from app.core.config import settings
from app.core.security import create_access_token
from app.db.base import Base
from app.db.redis import get_redis
from app.db.session import get_session
from app.main import app
from app.models.profile import UserProfile
from app.models.user import AppUser
from app.services import oauth
from app.services.auth import pkce_challenge
from app.services.oauth import OAuthError, SocialUser

APP_URI = "safebrother://auth"
PROFILE = {"lump_sum": 10_000_000, "monthly_saving": 100_000, "period_months": 12}


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
    monkeypatch.setattr(settings, "JWT_SECRET", "app-auth-test-" + "x" * 32)
    monkeypatch.setattr(settings, "ENV", "local")
    monkeypatch.setattr(settings, "BACKEND_PUBLIC_URL", "http://testserver")
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://front")
    monkeypatch.setattr(settings, "APP_REDIRECT_URI", APP_URI)
    monkeypatch.setattr(settings, "KAKAO_CLIENT_ID", "kakao-id")
    monkeypatch.setattr(settings, "KAKAO_CLIENT_SECRET", "kakao-secret")


@pytest.fixture
async def maker(async_db_url):
    engine = create_async_engine(async_db_url)
    yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    await engine.dispose()


@pytest.fixture
async def client(maker):
    redis = FakeAsyncRedis(decode_responses=True)

    async def _session():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_redis] = lambda: redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()


def fake_provider(monkeypatch, result: SocialUser | Exception | None = None) -> None:
    result = result or SocialUser("KAKAO", uuid.uuid4().hex, None, "덕환")

    async def _fetch_user(provider, code):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(oauth, "fetch_user", _fetch_user)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def app_login(client: AsyncClient, verifier: str) -> str:
    """외부 브라우저에서 일어나는 일: login → 소셜사 → callback. 앱 딥링크 주소를 돌려준다."""
    res = await client.get(
        "/api/v1/auth/kakao/login", params={"client": "app", "code_challenge": pkce_challenge(verifier)}
    )
    assert res.status_code == 302
    state = parse_qs(urlparse(res.headers["location"]).query)["state"][0]
    res = await client.get("/api/v1/auth/kakao/callback", params={"code": "c", "state": state})
    assert res.status_code == 302
    return res.headers["location"]


def code_of(deeplink: str) -> str:
    assert deeplink.startswith(f"{APP_URI}?")
    return parse_qs(urlparse(deeplink).query)["code"][0]


def new_verifier() -> str:
    return secrets.token_urlsafe(48)  # 64자


# ── 헤더로 인증 ───────────────────────────────────────────────


async def test_access_token_in_header_is_login(client, maker):
    async with maker() as session:
        user = AppUser(nickname="헤더")
        session.add(user)
        await session.commit()
    res = await client.get("/api/v1/users/me", headers=bearer(create_access_token(user.user_id)))
    assert res.status_code == 200 and res.json()["user_id"] == user.user_id


@pytest.mark.parametrize("header", ["Bearer ", "Basic abc", "bearer not-a-jwt", "Token x"])
async def test_bad_authorization_header_is_not_login(client, header):
    assert (await client.get("/api/v1/users/me", headers={"Authorization": header})).status_code == 401


async def test_guest_token_in_header_owns_profile(client, maker):
    guest_token = (await client.post("/api/v1/auth/app/guest")).json()["guest_token"]
    res = await client.post("/api/v1/profiles", json=PROFILE, headers=bearer(guest_token))
    assert res.status_code == 201
    assert "guest_token" not in client.cookies  # 헤더로 왔으면 게스트를 새로 만들지 않는다

    async with maker() as session:
        owner = await session.get(AppUser, res.json()["user_id"])
    assert owner.nickname == "guest"
    # 같은 게스트 토큰이면 로그인 전 API 도 쓸 수 있고, 토큰이 없으면 401
    assert (await client.get("/api/v1/users/me/roadmap", headers=bearer(guest_token))).status_code == 200
    assert (await client.get("/api/v1/users/me/roadmap")).status_code == 401
    # 게스트 토큰은 로그인이 아니다
    assert (await client.get("/api/v1/users/me", headers=bearer(guest_token))).status_code == 401


# ── 앱 로그인 ─────────────────────────────────────────────────


async def test_app_login_returns_tokens_via_one_time_code(client, monkeypatch):
    fake_provider(monkeypatch)
    verifier = new_verifier()
    deeplink = await app_login(client, verifier)
    assert not client.cookies.get("access_token")  # 앱 로그인은 쿠키를 굽지 않는다

    res = await client.post("/api/v1/auth/app/token", json={"code": code_of(deeplink), "code_verifier": verifier})
    assert res.status_code == 200
    tokens = res.json()
    assert tokens["token_type"] == "bearer" and tokens["expires_in"] == settings.ACCESS_TOKEN_MINUTES * 60
    me = await client.get("/api/v1/users/me", headers=bearer(tokens["access_token"]))
    assert me.json()["nickname"] == "덕환" and me.json()["is_guest"] is False


async def test_app_login_requires_code_challenge(client):
    res = await client.get("/api/v1/auth/kakao/login", params={"client": "app"})
    assert res.status_code == 422
    res = await client.get("/api/v1/auth/kakao/login", params={"client": "app", "code_challenge": "too-short"})
    assert res.status_code == 422


async def test_one_time_code_needs_matching_verifier_and_dies_after_use(client, monkeypatch):
    fake_provider(monkeypatch)
    verifier = new_verifier()
    code = code_of(await app_login(client, verifier))

    # 코드를 가로챈 쪽은 verifier 를 모른다. 한 번 틀리면 코드도 죽는다
    wrong = await client.post("/api/v1/auth/app/token", json={"code": code, "code_verifier": new_verifier()})
    assert wrong.status_code == 400
    again = await client.post("/api/v1/auth/app/token", json={"code": code, "code_verifier": verifier})
    assert again.status_code == 400

    code = code_of(await app_login(client, verifier))
    assert (await client.post("/api/v1/auth/app/token", json={"code": code, "code_verifier": verifier})).is_success
    reused = await client.post("/api/v1/auth/app/token", json={"code": code, "code_verifier": verifier})
    assert reused.status_code == 400


@pytest.mark.parametrize(
    ("callback_params", "provider_result", "reason"),
    [
        ({"error": "access_denied"}, None, "cancelled"),
        ({"code": "c"}, OAuthError("boom"), "provider_error"),
    ],
)
async def test_app_login_failure_goes_back_to_app(client, monkeypatch, callback_params, provider_result, reason):
    fake_provider(monkeypatch, provider_result)
    res = await client.get(
        "/api/v1/auth/kakao/login", params={"client": "app", "code_challenge": pkce_challenge(new_verifier())}
    )
    state = parse_qs(urlparse(res.headers["location"]).query)["state"][0]
    res = await client.get("/api/v1/auth/kakao/callback", params={"state": state, **callback_params})
    assert res.headers["location"] == f"{APP_URI}?error={reason}"


async def test_app_login_adopts_guest_records(client, maker, monkeypatch):
    guest_token = (await client.post("/api/v1/auth/app/guest")).json()["guest_token"]
    profile = (await client.post("/api/v1/profiles", json=PROFILE, headers=bearer(guest_token))).json()
    guest_id = profile["user_id"]

    fake_provider(monkeypatch)
    verifier = new_verifier()
    code = code_of(await app_login(client, verifier))
    tokens = (
        await client.post(
            "/api/v1/auth/app/token", json={"code": code, "code_verifier": verifier, "guest_token": guest_token}
        )
    ).json()

    me = (await client.get("/api/v1/users/me", headers=bearer(tokens["access_token"]))).json()
    async with maker() as session:
        assert (await session.get(UserProfile, profile["profile_id"])).user_id == me["user_id"]
        assert await session.get(AppUser, guest_id) is None
    # 옮겨진 게스트 토큰은 더 이상 아무 것도 못 연다
    assert (await client.get("/api/v1/users/me/roadmap", headers=bearer(guest_token))).status_code == 401


# ── refresh / logout ────────────────────────────────────────


async def test_app_refresh_rotates_with_body(client, monkeypatch):
    fake_provider(monkeypatch)
    verifier = new_verifier()
    code = code_of(await app_login(client, verifier))
    first = (await client.post("/api/v1/auth/app/token", json={"code": code, "code_verifier": verifier})).json()

    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert res.status_code == 200
    second = res.json()
    assert second["refresh_token"] != first["refresh_token"]
    assert (await client.get("/api/v1/users/me", headers=bearer(second["access_token"]))).status_code == 200
    # 쓴 refresh 토큰은 죽는다
    old = await client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert old.status_code == 401


async def test_app_logout_revokes_refresh_from_body(client, monkeypatch):
    fake_provider(monkeypatch)
    verifier = new_verifier()
    code = code_of(await app_login(client, verifier))
    tokens = (await client.post("/api/v1/auth/app/token", json={"code": code, "code_verifier": verifier})).json()

    logout = await client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert logout.status_code == 204
    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 401
