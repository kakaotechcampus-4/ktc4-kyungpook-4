"""챗봇 '기타' 우대조건 질문/답 (services/chatbot.py, api/v1/profiles.py). DB 와 AI 호출 없이 돈다."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app
from app.services import chatbot
from app.services.chatbot import EtcAnswerResult, EtcQuestion, recommended_options, select_question_targets


def _cond(cid, ctype="기타", bonus="0.30", product="P1", pmin=None, pmax=None):
    return SimpleNamespace(
        condition_id=cid,
        condition_type=ctype,
        rate_bonus=None if bonus is None else Decimal(bonus),
        product_id=product,
        applies_period_min=pmin,
        applies_period_max=pmax,
    )


def _option(base="3.00", max_="4.00", period=12):
    return SimpleNamespace(base_rate=Decimal(base), max_rate=Decimal(max_), period_months=period)


# --- 질문 대상 고르기 ---------------------------------------------------------


def test_targets_only_etc_with_bonus_not_yet_answered():
    conds = [
        _cond("A"),
        _cond("B", ctype="급여이체"),  # 고정 조건은 STEP2 가 묻는다
        _cond("C", bonus=None),  # 우대폭이 없으면 답해도 계산이 안 바뀐다
        _cond("D"),  # 이미 답함
    ]
    targets = select_question_targets(conds, {"P1": _option()}, answered_ids={"D"})
    assert [c.condition_id for c in targets] == ["A"]


def test_targets_skip_options_without_room_for_bonus():
    # 최고금리 = 기본금리면 우대금리가 붙을 여지가 없다 (지금 새마을금고 데이터가 전부 이렇다)
    conds = [_cond("A", product="P1"), _cond("B", product="P2")]
    options = {"P1": _option(base="3.00", max_="3.00"), "P2": _option()}
    assert [c.condition_id for c in select_question_targets(conds, options, set())] == ["B"]


def test_targets_respect_period_and_recommended_products():
    conds = [
        _cond("A", pmin=24),  # 24개월 이상에만 적용 - 12개월 옵션이라 제외
        _cond("B", pmax=12),
        _cond("C", product="NOT_RECOMMENDED"),  # 추천 결과에 없는 상품
    ]
    assert [c.condition_id for c in select_question_targets(conds, {"P1": _option(period=12)}, set())] == ["B"]


def test_recommended_options_collects_all_tiers_but_not_baseline():
    def alloc(pid):
        return SimpleNamespace(product=SimpleNamespace(product_id=pid), option=_option())

    plan = SimpleNamespace(
        tiers={
            "단순형": SimpleNamespace(deposit_allocs=[alloc("P1")], installment_allocs=[]),
            "최대형": SimpleNamespace(deposit_allocs=[alloc("P1")], installment_allocs=[alloc("P2")]),
        },
        baseline=SimpleNamespace(deposit_allocs=[alloc("BASE")], installment_allocs=[]),
    )
    assert set(recommended_options(plan)) == {"P1", "P2"}


# --- API ------------------------------------------------------------------------


class _FakeSession:
    """프로필 조회만 흉내 낸다. profile_id 1 만 있다."""

    async def get(self, model, pk):
        return SimpleNamespace(profile_id=pk) if pk == 1 else None


@pytest.fixture
def client():
    async def fake_session():
        yield _FakeSession()

    app.dependency_overrides[get_session] = fake_session
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


def test_questions_api(client, monkeypatch):
    async def fake_build(session, profile):
        return [EtcQuestion("앱으로 처음 가입하셨나요?", "당행 앱 최초 가입 고객", ["C1", "C2"])]

    monkeypatch.setattr(chatbot, "build_questions", fake_build)
    r = client.post("/api/v1/profiles/1/etc-questions")
    assert r.status_code == 200
    assert r.json() == {
        "questions": [
            {
                "question": "앱으로 처음 가입하셨나요?",
                "evidence_text": "당행 앱 최초 가입 고객",
                "condition_ids": ["C1", "C2"],
            }
        ]
    }


def test_questions_api_unknown_profile(client):
    assert client.post("/api/v1/profiles/999/etc-questions").status_code == 404


def test_answers_api(client, monkeypatch):
    received = {}

    async def fake_save(session, profile, answers):
        received["answers"] = answers
        return [EtcAnswerResult(a.condition_ids, a.answer == "네") for a in answers]

    monkeypatch.setattr(chatbot, "save_answers", fake_save)
    body = {
        "answers": [
            {"condition_ids": ["C1", "C2"], "question": "q1", "answer": "  네  "},
            {"condition_ids": ["C3"], "question": "q2", "answer": "아니요"},
        ]
    }
    r = client.post("/api/v1/profiles/1/etc-answers", json=body)
    assert r.status_code == 200
    assert r.json() == {
        "results": [{"condition_ids": ["C1", "C2"], "met": True}, {"condition_ids": ["C3"], "met": False}]
    }
    assert received["answers"][0].answer == "네"  # 앞뒤 공백은 지우고 넘긴다


@pytest.mark.parametrize(
    "body",
    [
        {"answers": []},
        {"answers": [{"condition_ids": [], "question": "q", "answer": "네"}]},
        {"answers": [{"condition_ids": ["C1"], "question": "q", "answer": "   "}]},
    ],
)
def test_answers_api_rejects_empty(client, body):
    assert client.post("/api/v1/profiles/1/etc-answers", json=body).status_code == 422


def test_answers_api_rejects_non_etc_condition(client, monkeypatch):
    async def fake_save(session, profile, answers):
        raise chatbot.UnknownConditionError(["X"])

    monkeypatch.setattr(chatbot, "save_answers", fake_save)
    body = {"answers": [{"condition_ids": ["X"], "question": "q", "answer": "네"}]}
    r = client.post("/api/v1/profiles/1/etc-answers", json=body)
    assert r.status_code == 422
    assert "X" in r.json()["detail"]