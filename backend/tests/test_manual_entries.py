"""캘린더 직접 기록: 기관별 상품 목록(GET /products)과 기록 저장·조회·삭제(/manual-entries).

DB 는 테스트 DB 를 쓴다. 안 떠 있으면 conftest 가 skip 한다.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401  - Base.metadata 를 채운다
from app.core.config import settings
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.product import Product
from app.models.user import AppUser

KB = "BANK-0010927"  # onboarding.BANK_CODES["국민은행"]


@pytest.fixture(scope="module")
def async_db_url(test_database_url):
    eng = create_engine(test_database_url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(eng)
    eng.dispose()
    return test_database_url.replace("postgresql+psycopg2", "postgresql+asyncpg")


@pytest.fixture(scope="module")
def seeded(async_db_url, test_database_url):
    """임포트 2번: 1번에만 있던 상품은 판매 종료, 2번에 있는 상품은 판매 중."""
    eng = create_engine(test_database_url)
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO batch_run (batch_type, status, finished_at) VALUES "
                "('COLLECT', 'SUCCESS', now()), ('COLLECT', 'SUCCESS', now()), ('COLLECT', 'FAILED', now())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO institution (institution_code, name, institution_type) VALUES "
                f"('{KB}', '국민은행', '은행'), ('CU-1', '대구신협', '신협'), ('CU-2', '부산신협', '신협')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO institution (institution_code, name, institution_type, region) VALUES "
                "('MG-1', '가창새마을금고 본점', '새마을금고', '대구 달성군'), "
                "('MG-2', '상품없는새마을금고 본점', '새마을금고', '부산 중구')"
            )
        )
    eng.dispose()
    return async_db_url


@pytest.fixture
async def maker(seeded):
    engine = create_async_engine(seeded)
    yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    await engine.dispose()


@pytest.fixture(scope="module", autouse=True)
def _products(seeded, test_database_url):
    eng = create_engine(test_database_url)
    rows = [
        # product_id, institution, name, type, run_id
        ("KB-SAVE-NEW", KB, "KB 새 적금", "적금", 2),
        ("KB-SAVE-OLD", KB, "KB 옛 적금", "적금", 1),  # 2번 임포트에 없음 -> 판매 종료
        ("KB-DEP", KB, "KB 정기예금", "예금", 2),
        ("CU-1-A", "CU-1", "정기예탁금", "예탁금", 2),
        ("CU-2-A", "CU-2", "정기예탁금", "예탁금", 2),  # 조합이 달라도 이름이 같으면 하나로 묶인다
        ("CU-2-B", "CU-2", "자유적립적금", "적금", 1),
        ("MG-1-A", "MG-1", "MG 정기예탁금", "예탁금", 2),
    ]
    with eng.begin() as conn:
        for pid, inst, name, kind, run in rows:
            conn.execute(
                text(
                    "INSERT INTO product (product_id, run_id, institution_code, product_name, product_type) "
                    "VALUES (:p, :r, :i, :n, :t)"
                ),
                {"p": pid, "r": run, "i": inst, "n": name, "t": kind},
            )
        for pid, months, base, top in [
            ("KB-SAVE-NEW", 12, 3.0, 4.5),
            ("KB-SAVE-NEW", 6, 2.8, 4.0),
            ("KB-SAVE-OLD", 12, 2.0, 2.5),
            ("CU-1-A", 12, 3.5, 3.5),
            ("CU-2-A", 6, 3.3, 3.3),
            ("MG-1-A", 12, 3.1, 3.6),
        ]:
            conn.execute(
                text(
                    "INSERT INTO product_option (option_id, product_id, period_months, base_rate, max_rate) "
                    "VALUES (:o, :p, :m, :b, :t)"
                ),
                {"o": f"{pid}-{months}", "p": pid, "m": months, "b": base, "t": top},
            )
    eng.dispose()


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET", "manual-entry-test-" + "x" * 32)


@pytest.fixture
async def client(maker):
    async def _session():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()


async def login_as_new_user(client: AsyncClient, maker) -> int:
    async with maker() as session:
        user = AppUser(nickname="기록자")
        session.add(user)
        await session.commit()
        user_id = user.user_id
    client.cookies.set("access_token", create_access_token(user_id))
    return user_id


# ── 기관별 상품 목록 ────────────────────────────────────────


async def test_bank_products_on_sale_first(client):
    res = await client.get("/api/v1/products", params={"institution": "국민은행"})
    body = res.json()
    assert res.status_code == 200
    assert body["grouped_by_name"] is False
    assert [(i["product_name"], i["on_sale"]) for i in body["items"]] == [
        ("KB 정기예금", True),
        ("KB 새 적금", True),
        ("KB 옛 적금", False),  # 최근 성공 임포트(2번)에 없다. 실패한 3번은 기준이 아니다
    ]
    new = body["items"][1]
    assert (new["product_id"], new["periods"], new["base_rate"], new["max_rate"]) == ("KB-SAVE-NEW", [6, 12], 3.0, 4.5)
    assert body["items"][0]["periods"] == []  # 옵션이 없어도 상품은 보인다


async def test_filter_by_product_type(client):
    res = await client.get("/api/v1/products", params={"institution": "국민은행", "product_type": "예금"})
    assert [i["product_name"] for i in res.json()["items"]] == ["KB 정기예금"]


async def test_coop_products_grouped_by_name(client):
    body = (await client.get("/api/v1/products", params={"institution": "신협"})).json()
    assert body["grouped_by_name"] is True
    assert [(i["product_name"], i["on_sale"], i["periods"]) for i in body["items"]] == [
        ("정기예탁금", True, [6, 12]),  # 대구·부산 두 조합 것이 하나로
        ("자유적립적금", False, []),
    ]
    assert all(i["product_id"] is None and i["max_rate"] is None for i in body["items"])


async def test_coop_branches(client):
    body = (await client.get("/api/v1/products/branches", params={"institution": "새마을금고"})).json()
    # 상품이 없는 지점은 뺀다. 지역을 붙여 '대구'로 검색되게 한다
    assert body["items"] == [
        {
            "institution_code": "MG-1",
            "name": "가창새마을금고 본점",
            "region": "대구 달성군",
            "label": "가창새마을금고 본점 (대구 달성군)",
        }
    ]
    cu = (await client.get("/api/v1/products/branches", params={"institution": "신협"})).json()
    assert [i["label"] for i in cu["items"]] == ["대구신협", "부산신협"]


async def test_branches_only_for_coops(client):
    res = await client.get("/api/v1/products/branches", params={"institution": "국민은행"})
    assert res.status_code == 422


async def test_coop_branch_products_have_rates(client):
    """지점을 고르면 이름으로 묶지 않고 그 지점 상품을 금리와 함께 준다."""
    body = (await client.get("/api/v1/products", params={"institution": "신협", "branch": "CU-1"})).json()
    assert body["grouped_by_name"] is False
    assert [(i["product_id"], i["product_name"], i["base_rate"], i["max_rate"]) for i in body["items"]] == [
        ("CU-1-A", "정기예탁금", 3.5, 3.5)
    ]
    mg = (await client.get("/api/v1/products", params={"institution": "새마을금고", "branch": "MG-1"})).json()
    assert [(i["product_id"], i["max_rate"]) for i in mg["items"]] == [("MG-1-A", 3.6)]


async def test_branch_of_other_type_is_empty(client):
    res = await client.get("/api/v1/products", params={"institution": "새마을금고", "branch": "CU-1"})
    assert res.json()["items"] == []
    bank = await client.get("/api/v1/products", params={"institution": "국민은행", "branch": "CU-1"})
    assert [i["product_id"] for i in bank.json()["items"]] == ["KB-DEP", "KB-SAVE-NEW", "KB-SAVE-OLD"]  # 은행은 무시


async def test_institution_without_data_is_empty(client):
    body = (await client.get("/api/v1/products", params={"institution": "씨티은행"})).json()
    assert body["items"] == []


async def test_unknown_institution_is_422(client):
    assert (await client.get("/api/v1/products", params={"institution": "없는은행"})).status_code == 422


# ── 직접 기록 ───────────────────────────────────────────────


def entry(**kw) -> dict:
    return {
        "entry_date": "2026-11-05",
        "institution_name": "국민은행",
        "product_name": "KB 새 적금",
        "amount": 300_000,
    } | kw


async def test_requires_login(client):
    assert (await client.get("/api/v1/manual-entries")).status_code == 401
    assert (await client.post("/api/v1/manual-entries", json=entry())).status_code == 401


async def test_create_from_product_list(client, maker):
    await login_as_new_user(client, maker)
    res = await client.post("/api/v1/manual-entries", json=entry(product_id="KB-SAVE-NEW", memo="  "))
    body = res.json()
    assert res.status_code == 201
    assert (body["product_id"], body["product_name"], body["amount"]) == ("KB-SAVE-NEW", "KB 새 적금", 300_000)
    assert body["memo"] is None  # FE 가 빈 메모로 보내면 None


@pytest.mark.parametrize(
    "bad",
    [{"product_id": "NOPE"}, {"amount": 0}, {"product_name": "   "}, {"entry_date": "2026-13-01"}],
)
async def test_invalid_entry_is_422(client, maker, bad):
    await login_as_new_user(client, maker)
    assert (await client.post("/api/v1/manual-entries", json=entry(**bad))).status_code == 422


async def test_list_by_range_in_date_order(client, maker):
    await login_as_new_user(client, maker)
    for day in ["2026-11-08", "2026-11-02", "2026-11-09", "2026-11-01"]:
        await client.post("/api/v1/manual-entries", json=entry(entry_date=day))

    res = await client.get("/api/v1/manual-entries", params={"start": "2026-11-02", "end": "2026-11-08"})
    assert [e["entry_date"] for e in res.json()] == ["2026-11-02", "2026-11-08"]
    assert len((await client.get("/api/v1/manual-entries")).json()) == 4
    bad = await client.get("/api/v1/manual-entries", params={"start": "2026-11-08", "end": "2026-11-02"})
    assert bad.status_code == 422


async def test_others_entries_are_invisible(client, maker):
    await login_as_new_user(client, maker)
    entry_id = (await client.post("/api/v1/manual-entries", json=entry())).json()["entry_id"]

    await login_as_new_user(client, maker)  # 다른 사람
    assert (await client.get("/api/v1/manual-entries")).json() == []
    assert (await client.delete(f"/api/v1/manual-entries/{entry_id}")).status_code == 404


async def test_delete(client, maker):
    await login_as_new_user(client, maker)
    entry_id = (await client.post("/api/v1/manual-entries", json=entry())).json()["entry_id"]
    assert (await client.delete(f"/api/v1/manual-entries/{entry_id}")).status_code == 204
    assert (await client.get("/api/v1/manual-entries")).json() == []
    assert (await client.delete(f"/api/v1/manual-entries/{entry_id}")).status_code == 404


async def test_entry_survives_product_removal(client, maker):
    """상품이 지워져도 기록은 남고 product_id 만 비워진다."""
    await login_as_new_user(client, maker)
    async with maker() as session:
        session.add(Product(product_id="TMP", institution_code=KB, product_name="곧 사라질 상품", product_type="예금"))
        await session.commit()
    await client.post("/api/v1/manual-entries", json=entry(product_id="TMP", product_name="곧 사라질 상품"))
    async with maker() as session:
        await session.delete(await session.get(Product, "TMP"))
        await session.commit()

    [kept] = (await client.get("/api/v1/manual-entries")).json()
    assert (kept["product_id"], kept["product_name"]) == (None, "곧 사라질 상품")
