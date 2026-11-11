"""챗봇 '기타' 우대조건 질문/답 (services/chatbot.py, api/v1/profiles.py). DB 와 AI 호출 없이 돈다."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from ktc4_ai import condition_qa

from app.api.deps import get_principal
from app.db.session import get_session
from app.main import app
from app.services import chatbot
from app.services.chatbot import (
    EtcAnswerResult,
    EtcQuestion,
    label_question,
    recommended_options,
    select_question_targets,
)
from app.services.portfolio import institution_display_name


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


def test_targets_skip_promo_rate():
    # 특판우대이율은 조건이 아니라 판촉 금리 - 이미 충족으로 계산하므로 묻지 않는다
    promo = _cond("A")
    promo.evidence_text = "특판우대이율"
    conds = [promo, _cond("B")]
    assert [c.condition_id for c in select_question_targets(conds, {"P1": _option()}, set())] == ["B"]


def test_institution_display_name():
    assert institution_display_name("가락", "신협") == "가락신협"
    assert institution_display_name("가락신협", "신협") == "가락신협"
    assert institution_display_name("주식회사 카카오뱅크", "은행") == "카카오뱅크"
    assert institution_display_name("농협은행주식회사", "은행") == "농협은행"
    assert institution_display_name("토스뱅크 주식회사", "은행") == "토스뱅크"
    assert institution_display_name("도봉새마을금고 본점", "새마을금고") == "도봉새마을금고 본점"


def test_label_question_names_institution_and_product():
    info = {"P1": ("I1", "가락신협", "A적금"), "P2": ("I1", "가락신협", "B적금")}
    q = "장기거래고객에 해당하시나요?"
    assert label_question(q, ["P1"], info) == "가락신협 'A적금'의 우대조건이에요.\n" + q
    # 같은 기관의 상품 둘이 묶인 질문 (같은 상품의 조건이 여러 개여도 한 번만 센다)
    assert label_question(q, ["P1", "P2", "P1"], info).startswith("가락신협 'A적금' 외 1개 상품의 우대조건이에요.\n")
    assert label_question(q, ["UNKNOWN"], info) == q  # 이름을 못 찾으면 질문 그대로


def test_same_text_is_asked_per_institution(monkeypatch):
    # 원문이 같아도 기관이 다르면 따로 묻는다. 질문 문장(AI)은 원문마다 한 번만 만든다
    calls = []
    monkeypatch.setattr(condition_qa, "_build_question_ai", lambda text: calls.append(text) or f"Q:{text}")
    text = "개설 금고에 화수분 통장을 보유한 경우"
    conds = [
        {"condition_id": "A1", "condition_type": "기타", "rate_bonus": 0.1, "evidence_text": text, "group_key": "G1"},
        {"condition_id": "A2", "condition_type": "기타", "rate_bonus": 0.1, "evidence_text": text, "group_key": "G1"},
        {"condition_id": "B1", "condition_type": "기타", "rate_bonus": 0.1, "evidence_text": text, "group_key": "G2"},
    ]
    groups = condition_qa.build_etc_questions(conds)
    assert [g["condition_ids"] for g in groups] == [["A1", "A2"], ["B1"]]
    assert calls == [text]


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


_OWNER_ID = 7


class _FakeSession:
    """프로필 조회만 흉내 낸다. profile_id 1 만 있다."""

    async def get(self, model, pk):
        # 프로필 주인은 아래 fixture 가 로그인시킨 사용자(7)
        return SimpleNamespace(profile_id=pk, user_id=_OWNER_ID) if pk == 1 else None


@pytest.fixture
def client():
    async def fake_session():
        yield _FakeSession()

    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_principal] = lambda: SimpleNamespace(user_id=_OWNER_ID)
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_principal, None)


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
        status = {"네": "met", "아니요": "not_met"}
        return [EtcAnswerResult(a.condition_ids, status.get(a.answer, "unsure")) for a in answers]

    monkeypatch.setattr(chatbot, "save_answers", fake_save)
    body = {
        "answers": [
            {"condition_ids": ["C1", "C2"], "question": "q1", "answer": "  네  "},
            {"condition_ids": ["C3"], "question": "q2", "answer": "아니요"},
            {"condition_ids": ["C4"], "question": "q3", "answer": "모르겠어요"},
        ]
    }
    r = client.post("/api/v1/profiles/1/etc-answers", json=body)
    assert r.status_code == 200
    assert r.json() == {
        "results": [
            {"condition_ids": ["C1", "C2"], "met": True, "status": "met"},
            {"condition_ids": ["C3"], "met": False, "status": "not_met"},
            {"condition_ids": ["C4"], "met": False, "status": "unsure"},
        ]
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


# --- 답 해석 (ktc4_ai.condition_qa.parse_answer) -------------------------------


def test_parse_answer_keywords_without_ai(monkeypatch):
    calls = []
    monkeypatch.setattr(condition_qa, "_parse_answer_ai", lambda raw: calls.append(raw))
    assert condition_qa.parse_answer("네.") is True
    assert condition_qa.parse_answer("아니요") is False
    assert condition_qa.parse_answer("잘 모르겠어요?") is None  # 모름 - 미충족이 아니다
    assert calls == []  # 키워드로 끝나면 AI 를 부르지 않는다


def test_parse_answer_ambiguous_or_failed_ai_is_unsure(monkeypatch):
    monkeypatch.setattr(condition_qa, "_parse_answer_ai", lambda raw: None)  # 애매함(low) 또는 호출 실패
    assert condition_qa.parse_answer("가입은 했던 것 같은데 기억이 잘 안 나요") is None
