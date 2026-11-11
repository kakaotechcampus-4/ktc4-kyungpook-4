"""로그인 사용자 연결(게스트 쿠키·소유 확인·로그인 이관)과 로드맵 숫자.

이자 공식은 DB 없이, 나머지는 테스트 DB 와 fakeredis 로 돈다. DB 가 안 떠 있으면 conftest 가 skip 한다.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401  - Base.metadata 를 채운다
from app.core import clock
from app.core.clock import kst_date
from app.core.config import settings
from app.db.base import Base
from app.db.redis import get_redis
from app.db.session import get_session
from app.main import app
from app.models.portfolio import UserHolding, UserPortfolio
from app.models.profile import UserProfile
from app.models.user import AppUser
from app.services import oauth
from app.services import portfolio as portfolio_service
from app.services.oauth import SocialUser
from app.services.portfolio import _deposit_interest, _installment_interest
from app.services.roadmap import accrued, build_roadmap, elapsed_months

RATE = Decimal("4.00")


def _holding(**kw) -> UserHolding:
    base = {"base_rate": RATE, "effective_rate": RATE, "max_rate": RATE, "start_date": date(2026, 1, 1)}
    return UserHolding(**(base | kw))


# ── 이자 공식 (DB 없음) ──────────────────────────────────────


def test_matured_deposit_equals_recommend_formula():
    h = _holding(amount=10_000_000, maturity_date=date(2027, 1, 1))
    a = accrued(h, date(2027, 6, 1))
    assert a.interest == _deposit_interest(10_000_000, RATE, 12)  # 추천 화면에서 보여준 금액과 같다
    assert a.paid_principal == 10_000_000


def test_deposit_accrues_by_days():
    h = _holding(amount=10_000_000, maturity_date=date(2027, 1, 1))
    a = accrued(h, date(2026, 4, 11))  # 100일
    assert a.interest == Decimal(10_000_000) * RATE / 100 * 100 / 365


def test_installment_counts_only_paid_rounds():
    h = _holding(monthly_amount=100_000, maturity_date=date(2027, 1, 1))
    a = accrued(h, date(2026, 3, 1))  # 1/1, 2/1, 3/1 세 번 냈다 (3/1 분은 아직 이자 0)
    assert a.paid_principal == 300_000
    assert a.total_principal == 1_200_000
    expected = sum(Decimal(100_000) * RATE / 100 * days / 365 for days in (59, 28, 0))
    assert a.interest == expected


def test_matured_installment_equals_recommend_formula():
    h = _holding(monthly_amount=100_000, maturity_date=date(2027, 1, 1))
    assert accrued(h, date(2027, 1, 1)).interest == _installment_interest(100_000, RATE, 12)


def test_nothing_before_start():
    h = _holding(amount=1_000_000, maturity_date=date(2027, 1, 1))
    assert accrued(h, date(2025, 12, 31)).interest == 0


@pytest.mark.parametrize(
    ("start", "today", "expected"),
    [
        (date(2026, 1, 31), date(2026, 2, 27), 0),  # 한 달이 아직 안 찼다
        (date(2026, 1, 31), date(2026, 2, 28), 1),  # 31일이 없는 달은 말일에 한 달 (만기일 계산과 같은 규칙)
        (date(2026, 1, 15), date(2026, 1, 15), 0),
        (date(2026, 1, 15), date(2027, 1, 15), 12),
        (date(2026, 1, 15), date(2025, 1, 1), 0),
    ],
)
def test_elapsed_months(start, today, expected):
    assert elapsed_months(start, today) == expected


# ── DB · API ────────────────────────────────────────────────


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
    monkeypatch.setattr(settings, "JWT_SECRET", "roadmap-test-" + "x" * 32)
    monkeypatch.setattr(settings, "ENV", "local")
    monkeypatch.setattr(settings, "BACKEND_PUBLIC_URL", "http://testserver")
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://front")
    monkeypatch.setattr(settings, "KAKAO_CLIENT_ID", "kakao-id")
    monkeypatch.setattr(settings, "KAKAO_CLIENT_SECRET", "kakao-secret")


@pytest.fixture
async def maker(async_db_url):
    engine = create_async_engine(async_db_url)
    yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    await engine.dispose()


@pytest.fixture
def fake_recommend(monkeypatch):
    """추천 계산은 다른 테스트가 본다. 여기서는 소유 확인만 보므로 계산을 비운다."""

    async def build_tiers(session, profile):
        return SimpleNamespace(tiers={}, baseline=None)

    async def recommend_options(session, profile, plan, *, with_reason=True):
        return [], None

    monkeypatch.setattr(portfolio_service, "build_tiers", build_tiers)
    monkeypatch.setattr(portfolio_service, "recommend_options", recommend_options)


@pytest.fixture
async def clients(maker):
    """서로 다른 브라우저 두 개 (쿠키를 따로 가진다)."""
    redis = FakeAsyncRedis(decode_responses=True)

    async def _session():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_redis] = lambda: redis
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://testserver") as a,
        AsyncClient(transport=transport, base_url="http://testserver") as b,
    ):
        yield a, b
    app.dependency_overrides.clear()


PROFILE = {"lump_sum": 10_000_000, "monthly_saving": 100_000, "period_months": 12}


async def create_profile(client: AsyncClient) -> int:
    res = await client.post("/api/v1/profiles", json=PROFILE)
    assert res.status_code == 201
    return res.json()["profile_id"]


async def add_portfolio(
    maker, user_id: int, profile_id: int, *, status="진행중", closed_at=None, goal=None, **holding
) -> int:
    async with maker() as session:
        portfolio = UserPortfolio(
            user_id=user_id,
            profile_id=profile_id,
            portfolio_type="균형형",
            status=status,
            closed_at=closed_at,
            goal_amount=goal[0] if goal else None,
            goal_date=goal[1] if goal else None,
        )
        session.add(portfolio)
        await session.flush()
        session.add(
            UserHolding(
                portfolio_id=portfolio.portfolio_id,
                institution="테스트은행",
                product_name="테스트 상품",
                base_rate=RATE,
                effective_rate=RATE,
                max_rate=RATE,
                **holding,
            )
        )
        await session.commit()
        return portfolio.portfolio_id


async def test_profile_without_login_gets_guest_cookie(clients, maker):
    a, _ = clients
    profile_id = await create_profile(a)
    assert a.cookies.get("guest_token")
    async with maker() as session:
        owner = await session.get(AppUser, (await session.get(UserProfile, profile_id)).user_id)
    assert owner.nickname == "guest"

    await create_profile(a)  # 같은 브라우저는 같은 게스트를 쓴다
    async with maker() as session:
        count = await session.scalar(
            select(text("count(*)")).select_from(UserProfile).where(UserProfile.user_id == owner.user_id)
        )
    assert count == 2


async def test_only_owner_can_use_profile(clients, fake_recommend):
    a, b = clients
    profile_id = await create_profile(a)
    body = {"profile_id": profile_id, "with_reason": False}

    assert (await a.post("/api/v1/portfolios/recommend", json=body)).status_code == 200
    assert (await b.post("/api/v1/portfolios/recommend", json=body)).status_code == 401  # 쿠키 없음
    await create_profile(b)  # b 도 자기 게스트가 생긴다
    assert (await b.post("/api/v1/portfolios/recommend", json=body)).status_code == 404  # 남의 것
    assert (await b.post(f"/api/v1/profiles/{profile_id}/etc-questions")).status_code == 404


async def test_only_owner_can_see_calendar(clients, maker):
    a, b = clients
    profile_id = await create_profile(a)
    async with maker() as session:
        user_id = (await session.get(UserProfile, profile_id)).user_id
    portfolio_id = await add_portfolio(
        maker, user_id, profile_id, amount=1_000_000, start_date=date(2026, 1, 1), maturity_date=date(2026, 7, 1)
    )
    assert (await a.get(f"/api/v1/portfolios/{portfolio_id}/calendar")).status_code == 200
    await create_profile(b)
    assert (await b.get(f"/api/v1/portfolios/{portfolio_id}/calendar")).status_code == 404


async def test_new_selection_closes_previous(maker):
    async with maker() as session:
        user = AppUser(nickname="재확정")
        session.add(user)
        await session.flush()
        profile = UserProfile(user_id=user.user_id, capital=1_000_000, period_months=6)
        session.add(profile)
        await session.commit()
    first = await add_portfolio(
        maker, user.user_id, profile.profile_id, amount=1, start_date=date(2026, 1, 1), maturity_date=date(2026, 7, 1)
    )
    async with maker() as session:
        await portfolio_service.close_active_portfolios(session, user.user_id)
        await session.commit()
        closed = await session.get(UserPortfolio, first)
    assert closed.status == "완료" and closed.closed_at is not None


async def test_login_adopts_guest_records(clients, maker, monkeypatch):
    a, _ = clients
    profile_id = await create_profile(a)
    async with maker() as session:
        guest_id = (await session.get(UserProfile, profile_id)).user_id
    portfolio_id = await add_portfolio(
        maker, guest_id, profile_id, amount=1_000_000, start_date=date(2026, 1, 1), maturity_date=date(2027, 1, 1)
    )

    async def fetch_user(provider, code):
        return SocialUser("KAKAO", uuid.uuid4().hex, None, "덕환")

    monkeypatch.setattr(oauth, "fetch_user", fetch_user)
    login = await a.get("/api/v1/auth/kakao/login")
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    await a.get("/api/v1/auth/kakao/callback", params={"code": "c", "state": state})

    assert "guest_token" not in a.cookies  # 게스트 쿠키는 지운다
    me = (await a.get("/api/v1/users/me")).json()
    roadmap = (await a.get("/api/v1/users/me/roadmap")).json()
    assert roadmap["active_portfolio_id"] == portfolio_id  # 게스트 때 고른 안이 계정으로 왔다
    async with maker() as session:
        assert (await session.get(UserPortfolio, portfolio_id)).user_id == me["user_id"]
        assert (await session.get(UserProfile, profile_id)).user_id == me["user_id"]
        assert await session.get(AppUser, guest_id) is None


async def test_roadmap_requires_cookie(clients):
    a, _ = clients
    assert (await a.get("/api/v1/users/me/roadmap")).status_code == 401


async def test_roadmap_numbers(maker):
    today = date(2026, 7, 1)
    async with maker() as session:
        user = AppUser(nickname="로드맵", created_at=datetime(2026, 1, 1, tzinfo=UTC))
        session.add(user)
        await session.flush()
        profile = UserProfile(user_id=user.user_id, capital=10_000_000, monthly_saving=100_000, period_months=12)
        session.add(profile)
        await session.commit()
    uid, pid = user.user_id, profile.profile_id

    # 그만둔 안: 3/1 시작 예금을 5/1 에 그만뒀다 -> 61일치만
    old = {"amount": 5_000_000, "start_date": date(2026, 3, 1), "maturity_date": date(2027, 3, 1)}
    await add_portfolio(maker, uid, pid, status="완료", closed_at=datetime(2026, 5, 1, tzinfo=UTC), **old)
    # 진행중 안: 이미 만기된 예금 + 진행중 적금
    active = {"amount": 1_000_000, "start_date": date(2026, 1, 1), "maturity_date": date(2026, 4, 1)}
    active_id = await add_portfolio(maker, uid, pid, goal=(11_200_000, date(2027, 5, 1)), **active)
    running = {"monthly_amount": 100_000, "start_date": date(2026, 5, 1), "maturity_date": date(2027, 5, 1)}
    async with maker() as session:
        session.add(
            UserHolding(
                portfolio_id=active_id,
                institution="테스트은행",
                product_name="적금",
                base_rate=RATE,
                effective_rate=RATE,
                max_rate=RATE,
                **running,
            )
        )
        await session.commit()

    def after_tax(interest: Decimal) -> int:
        return int((interest * (1 - Decimal("0.154"))).to_integral_value())

    closed = after_tax(Decimal(5_000_000) * RATE / 100 * 61 / 365)
    matured = after_tax(_deposit_interest(1_000_000, RATE, 3))
    saving = after_tax(accrued(_holding(**running), today).interest)

    async with maker() as session:
        numbers = await build_roadmap(session, await session.get(AppUser, uid), today)
    assert numbers.started_at == date(2026, 1, 1)
    assert numbers.elapsed_months == 6
    assert numbers.total_interest == closed + matured + saving
    assert numbers.current_interest == saving  # 만기된 예금·그만둔 안은 '현재'가 아니다
    assert numbers.current_principal == 300_000  # 5/1, 6/1, 7/1 세 번
    assert numbers.active_portfolio_id == active_id
    # 목표 경로 위치는 만기된 예금(원금+이자)도 계속 센다 - 만기됐다고 아바타가 뒤로 가지 않는다
    assert numbers.active_total == 1_000_000 + matured + 300_000 + saving
    assert (numbers.goal_amount, numbers.goal_date) == (11_200_000, date(2027, 5, 1))


async def test_my_calendar_follows_account_not_browser(clients, maker, monkeypatch):
    """같은 계정으로 로그인하면 다른 브라우저에서도 진행중 안의 일정이 보인다."""
    a, b = clients
    account = SocialUser("KAKAO", uuid.uuid4().hex, None, "덕환")

    async def fetch_user(provider, code):
        return account

    monkeypatch.setattr(oauth, "fetch_user", fetch_user)

    async def login(client):
        res = await client.get("/api/v1/auth/kakao/login")
        state = parse_qs(urlparse(res.headers["location"]).query)["state"][0]
        await client.get("/api/v1/auth/kakao/callback", params={"code": "c", "state": state})

    assert (await a.get("/api/v1/users/me/calendar")).status_code == 401
    await login(a)
    assert (await a.get("/api/v1/users/me/calendar")).json() == []  # 아직 고른 안이 없다

    profile_id = await create_profile(a)  # 로그인 상태라 계정 것으로 만들어진다
    assert "guest_token" not in a.cookies
    user_id = (await a.get("/api/v1/users/me")).json()["user_id"]
    start = date.today()
    await add_portfolio(
        maker,
        user_id,
        profile_id,
        monthly_amount=100_000,
        start_date=start,
        maturity_date=portfolio_service._add_months(start, 6),
    )

    await login(b)  # 다른 브라우저, 같은 계정
    events = (await b.get("/api/v1/users/me/calendar")).json()
    assert len(events) == 7  # 납입 6회(가입일이 1회차) + 만기
    assert events == (await a.get("/api/v1/users/me/calendar")).json()


async def test_active_total_does_not_drop_at_maturity(maker):
    """예금이 만기되는 날을 지나도 목표 경로 위치(active_total)는 줄지 않고, current_* 만 빠진다."""
    async with maker() as session:
        user = AppUser(nickname="만기")
        session.add(user)
        await session.flush()
        profile = UserProfile(user_id=user.user_id, capital=1_000_000, period_months=6)
        session.add(profile)
        await session.commit()
    deposit = {"amount": 1_000_000, "start_date": date(2026, 1, 1), "maturity_date": date(2026, 7, 1)}
    await add_portfolio(maker, user.user_id, profile.profile_id, **deposit)

    async with maker() as session:
        u = await session.get(AppUser, user.user_id)
        before = await build_roadmap(session, u, date(2026, 6, 30))
        after = await build_roadmap(session, u, date(2026, 7, 2))
    assert after.active_total >= before.active_total
    assert (before.current_principal, after.current_principal) == (1_000_000, 0)
    assert after.goal_amount is None  # 목표가 없는 안이면 null


async def test_calendar_matches_roadmap_payment_days(maker, monkeypatch):
    """적금 1회차는 가입일(로드맵 계산과 같은 기준). 만기 일정은 적금·예금 모두 있고 금액이 붙는다."""
    today = date(2026, 1, 31)
    monkeypatch.setattr(clock, "today", lambda: today)
    async with maker() as session:
        user = AppUser(nickname="캘린더")
        session.add(user)
        await session.flush()
        profile = UserProfile(user_id=user.user_id, capital=1_000_000, monthly_saving=100_000, period_months=3)
        session.add(profile)
        await session.commit()
    saving = {"monthly_amount": 100_000, "start_date": today, "maturity_date": date(2026, 4, 30)}
    pid = await add_portfolio(maker, user.user_id, profile.profile_id, **saving)
    async with maker() as session:
        session.add(
            UserHolding(
                portfolio_id=pid,
                institution="예금은행",
                product_name="예금",
                base_rate=RATE,
                effective_rate=RATE,
                max_rate=RATE,
                amount=1_000_000,
                start_date=today,
                maturity_date=date(2026, 4, 30),
            )
        )
        await session.commit()
        events = await portfolio_service.get_calendar_events(session, pid)

    assert [(e.date, e.event_type, e.installment_round, e.amount, e.product_name) for e in events] == [
        (date(2026, 1, 31), "납입", 1, 100_000, "테스트 상품"),
        (date(2026, 2, 28), "납입", 2, 100_000, "테스트 상품"),  # 말일 보정
        (date(2026, 3, 31), "납입", 3, 100_000, "테스트 상품"),
        (date(2026, 4, 30), "만기", 0, 300_000, "테스트 상품"),
        (date(2026, 4, 30), "만기", 0, 1_000_000, "예금"),
    ]


def test_kst_date_handles_utc_midnight():
    # UTC 11/5 20:00 = 한국 11/6 05:00
    assert kst_date(datetime(2026, 11, 5, 20, 0, tzinfo=UTC)) == date(2026, 11, 6)
    assert kst_date(datetime(2026, 11, 5, 14, 59, tzinfo=UTC)) == date(2026, 11, 5)
