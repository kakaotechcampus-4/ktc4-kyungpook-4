"""결과 먼저, 추천 이유는 나중에 - /recommend 의 with_reason, /reasons. DB 와 AI 호출 없이 돈다."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_principal
from app.db.session import get_session
from app.main import app
from app.schemas.portfolio import PortfolioOptionOut
from app.services import portfolio as portfolio_service

_OWNER_ID = 7


class _FakeSession:
    async def get(self, model, pk):
        # 프로필 주인은 아래 fixture 가 로그인시킨 사용자(7)
        return SimpleNamespace(profile_id=pk, user_id=_OWNER_ID) if pk == 1 else None


@pytest.fixture
def client(monkeypatch):
    async def fake_session():
        yield _FakeSession()

    async def fake_build_tiers(session, profile):
        return SimpleNamespace(tiers={}, baseline=None)

    calls = []

    async def fake_recommend_options(session, profile, plan, *, with_reason=True):
        calls.append(with_reason)
        option = {
            "tier": "균형형",
            "products": [],
            "after_tax_total": 1000,
            "reason": "추천 이유" if with_reason else None,
            "extra_vs_baseline": None,
            "extra_vs_simple": None,
            "new_bank_count": 0,
            "required_actions": [],
            "tax_saving_won": 0,
            "over_comprehensive_tax": False,
        }
        return [PortfolioOptionOut(**option)], None

    monkeypatch.setattr(portfolio_service, "build_tiers", fake_build_tiers)
    monkeypatch.setattr(portfolio_service, "recommend_options", fake_recommend_options)
    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_principal] = lambda: SimpleNamespace(user_id=_OWNER_ID)
    yield TestClient(app), calls
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_principal, None)


def test_recommend_with_reason_by_default(client):
    c, calls = client
    r = c.post("/api/v1/portfolios/recommend", json={"profile_id": 1})
    assert r.status_code == 200
    assert r.json()["options"][0]["reason"] == "추천 이유"
    assert calls == [True]  # 기본값은 지금과 같다 - 앱이 바뀌기 전에도 그대로 동작


def test_recommend_without_reason(client):
    c, calls = client
    r = c.post("/api/v1/portfolios/recommend", json={"profile_id": 1, "with_reason": False})
    assert r.status_code == 200
    assert r.json()["options"][0]["reason"] is None
    assert calls == [False]


def test_reasons_api(client):
    c, calls = client
    r = c.post("/api/v1/portfolios/reasons", json={"profile_id": 1})
    assert r.status_code == 200
    assert r.json() == {"reasons": {"균형형": "추천 이유"}}
    assert calls == [True]


def test_reasons_api_unknown_profile(client):
    c, _ = client
    assert c.post("/api/v1/portfolios/reasons", json={"profile_id": 999}).status_code == 404
