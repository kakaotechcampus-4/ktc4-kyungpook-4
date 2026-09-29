"""
Step3 미니플로우① — 후보 상품 풀의 미해결 조건(condition)에 대해 질문을 만들고,
사용자의 자유텍스트 답변을 구조화된 값(boolean/숫자)으로 해석하는 모듈.
(claude/Step3_후보풀_미니플로우1_스펙_20260923.md 2~3장의 인터페이스를 코드로 옮긴 것)

AI 개입 범위 (PR #11 리뷰, junhee-ko 코멘트에 대한 답):
- 8~10개 고정 condition_type은 이 모듈이 결정론적 템플릿으로 질문을 만든다. AI 호출 없음.
- condition_type == "기타"인 조건만 evidence_text 원문을 보고 AI가 질문 문장을 생성한다.
- 사용자의 자유텍스트 답변은 AI를 한 번 호출해 기대 타입(boolean)으로 파싱한다.
- 파싱이 애매하거나("잘 모르겠어요" 포함) 실패하면 반드시 "조건 미충족"으로 보수적으로
  처리한다 — 계산값을 부풀리지 않는 방향. AI의 해석 결과를 곧이곧대로 신뢰하지 않는다.
- evidence_text 원문(공식 공시 텍스트) 자체의 정확성은 이 모듈의 검증 대상이 아니다 —
  소스 데이터의 정확성은 전제로 둔다(BE가 여기까지 재검증하지 않아도 됨).

애매하거나 실패한 경로는 전부 conservative_fallback() 한 곳을 거치도록 만들어서,
"애매하면 항상 미충족"이라는 규칙이 코드 구조로 강제되게 했다.

2026-09-29: FR-04 미니플로우① 구현 — 뼈대(스텁)였던 이 파일을 실제 동작하는 로직으로
채움(질문 템플릿 10종, '기타' 질문 생성/답변 파싱 AI 호출, 상호금융 조합원 여부
미니플로우① 포함).
"""
import json
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL  # noqa: E402


# ---------------------------------------------------------------------------
# AI 클라이언트 (extract_conditions_ai.py와 동일한 방식 - 엘리스 ML API, OpenAI 호환)
# ---------------------------------------------------------------------------
_client = None


def _get_client():
    """실제로 AI 호출이 필요할 때만 클라이언트를 만든다(지연 생성 - 이 모듈을
    import만 하고 고정 템플릿 경로만 쓰는 경우엔 API 키가 없어도 동작해야 하므로)."""
    global _client
    if _client is None:
        from openai import OpenAI  # 지연 import - 패키지 없이도 템플릿 경로는 동작하게

        if not OPENAI_API_KEY or not OPENAI_BASE_URL:
            raise RuntimeError(
                "OPENAI_API_KEY / OPENAI_BASE_URL이 .env에 설정 안 돼 있음 - "
                "AI 질문 생성/답변 파싱을 쓰려면 필요함(고정 템플릿 조건만 쓸 거면 "
                "이 함수를 호출하지 않으면 됨)."
            )
        _client = OpenAI(api_key=OPENAI_API_KEY, base_url=f"{OPENAI_BASE_URL}/v1")
    return _client


# ---------------------------------------------------------------------------
# 1) 고정 카테고리 질문 템플릿 (AI 호출 없음)
# ---------------------------------------------------------------------------
def _with_threshold(no_threshold: str, with_threshold: str):
    """threshold_value/threshold_unit이 있으면 그 값을 채운 문구, 없으면 일반 문구."""

    def _fn(condition: dict) -> str:
        tv = condition.get("threshold_value")
        tu = condition.get("threshold_unit")
        if tv is not None and tu:
            # 정수면 "50만원"처럼, 소수면 그대로 보여준다.
            tv_str = str(int(tv)) if float(tv).is_integer() else str(tv)
            return with_threshold.format(threshold_value=tv_str, threshold_unit=tu)
        return no_threshold

    return _fn


FIXED_TEMPLATES = {
    "급여이체": _with_threshold(
        "이 은행/조합으로 급여를 이체하실 건가요?",
        "이 은행/조합으로 급여를 월 {threshold_value}{threshold_unit} 이상 이체하실 건가요?",
    ),
    "자동이체": _with_threshold(
        "이 은행/조합 계좌로 각종 요금 자동이체를 설정하실 건가요?",
        "이 은행/조합 계좌로 자동이체를 월 {threshold_value}{threshold_unit} 이상 설정하실 건가요?",
    ),
    "신규고객": lambda c: "이 은행/조합의 신규 가입 고객이신가요? (최근 가입 또는 첫 거래)",
    "카드실적": _with_threshold(
        "이 은행/조합 체크·신용카드를 사용하실 건가요?",
        "이 은행/조합 카드를 월 {threshold_value}{threshold_unit} 이상 쓰실 건가요?",
    ),
    "마케팅동의": lambda c: "마케팅 정보 수신에 동의하실 건가요?",
    "공과금이체": _with_threshold(
        "이 은행/조합 계좌로 공과금을 자동이체 하실 건가요?",
        "이 은행/조합 계좌로 공과금을 월 {threshold_value}{threshold_unit} 이상 자동이체 하실 건가요?",
    ),
    "연금수령": lambda c: "이 은행/조합 계좌로 연금을 수령하실 건가요?",
    "비대면가입": lambda c: "비대면(모바일/인터넷)으로 가입하실 건가요?",
    "공제가입": lambda c: "관련 공제상품에 가입하실 건가요?",
    "연령조건": lambda c: "해당 연령 조건에 해당하시나요? (상품 상세 조건 참고)",
}


# ---------------------------------------------------------------------------
# 2) '기타' 조건: AI가 evidence_text를 보고 질문 문장 생성
# ---------------------------------------------------------------------------
_QUESTION_GEN_PROMPT = (
    "너는 예적금 우대조건 안내 챗봇이야. 아래는 어떤 예적금 상품의 우대조건 설명 원문이야. "
    "이 조건을 사용자가 충족하는지 물어보는 자연스러운 질문 문장 하나를 만들어줘.\n"
    "규칙:\n"
    "- 예/아니오로 답할 수 있는 질문 형태로 만들어.\n"
    "- 원문에 없는 내용을 지어내지 마. 원문의 의미를 벗어나지 마.\n"
    "- 질문 문장 하나만 출력해. 설명, 코드블록, 따옴표 없이 순수 텍스트로만."
)


def _build_question_ai(condition: dict) -> str:
    """'기타' 조건의 evidence_text(또는 description)를 보고 AI가 질문 문장을 생성.
    AI 호출이 실패하면(네트워크 오류 등) 원문을 그대로 보여주는 안전한 기본 문구로
    대체한다 - 질문 생성 실패가 전체 플로우를 중단시키면 안 되므로."""
    text = condition.get("evidence_text") or condition.get("description") or ""
    if not text:
        return "다음 우대조건에 해당하시나요? (상세 내용은 상품 설명 참고)"
    try:
        client = _get_client()
        res = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _QUESTION_GEN_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        question = (res.choices[0].message.content or "").strip()
        if question:
            return question
    except Exception:
        pass
    # AI 호출 실패 시 fallback: 원문을 그대로 인용해서라도 질문 형태를 유지
    return f'다음 조건에 해당하시나요? "{text}"'


def build_question(condition: dict) -> str:
    """condition_type이 고정 카테고리면 템플릿, '기타'면 AI 질문 생성."""
    condition_type = condition.get("condition_type", "기타")
    template = FIXED_TEMPLATES.get(condition_type)
    if template is not None:
        return template(condition)
    return _build_question_ai(condition)


# ---------------------------------------------------------------------------
# 3) 자유텍스트 답변 -> boolean 파싱 (애매하면 항상 미충족)
# ---------------------------------------------------------------------------
_YES_KEYWORDS = ("네", "예", "응", "충족", "해당", "네요", "그래", "맞아", "yes", "y")
_NO_KEYWORDS = ("아니", "아뇨", "미충족", "해당없음", "해당 없음", "no", "n")
_UNSURE_KEYWORDS = ("모르겠", "몰라", "글쎄", "잘 모름", "확실하지")

_ANSWER_PARSE_PROMPT = (
    "사용자의 자유 텍스트 답변을 boolean으로 해석해줘. "
    "'예/네/응/충족/해당함' 계열이면 true, "
    "'아니오/아니요/미충족/해당 안 됨' 계열이면 false, "
    "'모르겠다/잘 모르겠어요'거나 답변이 애매해서 예/아니오를 확정할 수 없으면 반드시 null. "
    "true / false / null 중 하나만, 다른 텍스트 설명 없이 정확히 그 단어만 출력해."
)


def conservative_fallback() -> bool:
    """애매하거나 파싱 실패 시 항상 이 값을 반환 — 조건 미충족(False)으로 취급.

    "AI 해석이 불확실하면 계산값을 부풀리지 않는다"는 규칙을 한 곳에 강제하기 위한 함수.
    parse_answer()의 모든 실패/애매 경로는 반드시 이 함수를 거친다."""
    return False


def _quick_keyword_match(raw_answer: str) -> Optional[bool]:
    """AI 호출 없이 바로 판단 가능한 아주 명확한 답변은 비용 절약을 위해 여기서 처리.
    조금이라도 애매하면 None을 반환해서 AI 파싱(_parse_answer_ai)으로 넘긴다."""
    text = (raw_answer or "").strip()
    if not text:
        return None
    if any(k in text for k in _UNSURE_KEYWORDS):
        return None  # "모르겠어요" 계열은 명확히 애매함 - AI/기본값으로
    # 부정 키워드를 긍정 키워드보다 먼저 체크(예: "아니요, 안 써요"에 다른 긍정어가
    # 안 섞여 있는 게 보통이라 순서 크게 중요하진 않지만 안전하게 부정 먼저)
    if any(k in text for k in _NO_KEYWORDS):
        return False
    if any(k in text for k in _YES_KEYWORDS):
        return True
    return None


def _parse_answer_ai(raw_answer: str) -> Optional[bool]:
    """AI에게 자유텍스트를 boolean으로 해석시킨다. 응답이 true/false가 아니면(null
    포함, 파싱 불가 포함) None을 반환 - 호출부에서 conservative_fallback()으로 처리."""
    try:
        client = _get_client()
        res = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _ANSWER_PARSE_PROMPT},
                {"role": "user", "content": raw_answer},
            ],
        )
        content = (res.choices[0].message.content or "").strip().lower()
        content = re.sub(r"[^a-z]", "", content)  # 코드펜스/마침표 등 잡음 제거
        if content == "true":
            return True
        if content == "false":
            return False
        return None  # "null" 또는 해석 불가한 응답
    except Exception:
        return None


def parse_answer(condition_type: str, raw_answer: str) -> bool:
    """자유텍스트 답변을 boolean으로 해석한다.

    순서: (1) 아주 명확한 키워드는 AI 호출 없이 바로 판정(비용 절약) ->
    (2) 그 외에는 AI 호출로 판정 -> (3) 그래도 애매/실패면 conservative_fallback().
    condition_type은 지금은 분기에 안 쓰지만, 나중에 카테고리별로 답변 해석 방식을
    다르게 하고 싶어질 수 있어서 인터페이스에 남겨둠."""
    quick = _quick_keyword_match(raw_answer)
    if quick is not None:
        return quick
    ai_result = _parse_answer_ai(raw_answer)
    if ai_result is not None:
        return ai_result
    return conservative_fallback()


# ---------------------------------------------------------------------------
# 4) Step3 2장 규칙 — 후보 풀에서 "물어볼 질문 목록" 만들기
# ---------------------------------------------------------------------------
def get_unresolved_conditions(candidate_products: list) -> list:
    """규칙 1: candidate_products를 순회하며 resolved=false이고 bonus_rate가 있는
    조건들의 condition_type 집합을 중복 제거해서 뽑는다. 대표로 각 condition_type의
    첫 조건(threshold 정보 포함)을 하나씩 남긴다(같은 타입끼리는 보통 threshold
    문구도 비슷해서 질문 하나로 충분 - Step3 스펙 2장 참고)."""
    seen = {}
    for product in candidate_products:
        for condition in product.get("conditions", []):
            if condition.get("resolved"):
                continue
            if condition.get("bonus_rate") is None:
                continue
            ctype = condition.get("condition_type", "기타")
            if ctype not in seen:
                seen[ctype] = condition
    return list(seen.values())


def _has_mutual_finance_membership(candidate_products: list) -> bool:
    """미니플로우① 트리거(Step3 3장): institution_type이 신협/새마을금고이고
    membership_required=true인 후보 상품이 하나라도 있는지."""
    for product in candidate_products:
        if product.get("institution_type") in ("신협", "새마을금고") and product.get(
            "membership_required"
        ):
            return True
    return False


MEMBERSHIP_QUESTION_TEMPLATE = (
    "혹시 {institution_name}조합원으로 가입되어 있으실까요? "
    "(계좌만 만든 경우는 조합원이 아닐 수 있어요 — 출자금(보통 1~5만원)을 냈다면 조합원입니다.)"
)
MEMBERSHIP_OPTIONS = ["네, 조합원이에요", "잘 모르겠어요", "계좌만 있어요"]


def build_membership_question(candidate_products: list) -> Optional[dict]:
    """미니플로우① 질문을 만든다. 트리거 조건이 아니면 None(질문 자체를 노출 안 함)."""
    if not _has_mutual_finance_membership(candidate_products):
        return None
    institution_names = sorted(
        {
            p.get("institution_type", "")
            for p in candidate_products
            if p.get("institution_type") in ("신협", "새마을금고") and p.get("membership_required")
        }
    )
    institution_name = "/".join(institution_names) + " " if institution_names else ""
    return {
        "kind": "membership",
        "question": MEMBERSHIP_QUESTION_TEMPLATE.format(institution_name=institution_name),
        "options": list(MEMBERSHIP_OPTIONS),
    }


def parse_membership_choice(choice: str) -> bool:
    """미니플로우① 답변 -> membership(boolean) 매핑 (Step3 3장, 보수적 처리:
    "네, 조합원이에요"만 True, 나머지("잘 모르겠어요"/"계좌만 있어요")는 전부 False)."""
    return choice.strip() == "네, 조합원이에요"


def build_question_list(candidate_products: list) -> list:
    """Step3 2장 규칙 1~4를 적용해서, 사용자에게 실제로 물어볼 질문 목록을 만든다.
    반환 형식: [{"kind": "condition", "condition_type": ..., "question": ...}, ...]
    맨 뒤에 미니플로우① 질문이 트리거되면 {"kind": "membership", ...}가 하나 더 붙는다.
    (규칙 5 - 답변 파싱/보수적 처리는 parse_answer()/parse_membership_choice()가 담당)"""
    questions = []
    for condition in get_unresolved_conditions(candidate_products):
        questions.append(
            {
                "kind": "condition",
                "condition_type": condition.get("condition_type", "기타"),
                "question": build_question(condition),
            }
        )
    membership_q = build_membership_question(candidate_products)
    if membership_q is not None:
        questions.append(membership_q)
    return questions


if __name__ == "__main__":
    # 간단한 자체 점검 - AI 호출 없이(고정 템플릿 경로만) 동작하는지 확인.
    # AI 경로('기타' 질문 생성, parse_answer)까지 실제로 테스트하려면
    # `python scripts/condition_qa.py --ai` 로 실행(.env에 OPENAI_API_KEY 필요).
    sample_candidate_products = [
        {
            "product_id": "CU-01235-1701-대면",
            "institution_type": "신협",
            "membership_required": True,
            "conditions": [
                {
                    "condition_id": "CU-01235-1701-대면-COND-1",
                    "condition_type": "급여이체",
                    "bonus_rate": 0.2,
                    "threshold_value": 50,
                    "threshold_unit": "만원",
                    "resolved": False,
                },
                {
                    "condition_id": "CU-01235-1701-대면-COND-2",
                    "condition_type": "마케팅동의",
                    "bonus_rate": 0.1,
                    "resolved": False,
                },
                {
                    "condition_id": "CU-01235-1701-대면-COND-3",
                    "condition_type": "기타",
                    "bonus_rate": None,  # bonus_rate 없는 조건은 질문 대상에서 제외(규칙 1)
                    "evidence_text": "주택청약종합저축 보유 시 우대",
                    "resolved": False,
                },
            ],
        }
    ]

    qs = build_question_list(sample_candidate_products)
    print("=== 고정 템플릿 질문 목록 (AI 호출 없음) ===")
    for q in qs:
        print(f"- [{q['kind']}] {q.get('condition_type', '')} -> {q['question']}")
        if q["kind"] == "membership":
            print(f"  선택지: {q['options']}")

    assert len(qs) == 3, f"기대: 급여이체+마케팅동의+membership 3개(기타/bonus_rate=None은 제외), got {len(qs)}"
    assert qs[0]["condition_type"] == "급여이체"
    assert "50만원" in qs[0]["question"]
    assert qs[1]["condition_type"] == "마케팅동의"
    assert qs[2]["kind"] == "membership"

    print()
    print("=== parse_answer 자체 점검 (키워드 경로, AI 호출 없음) ===")
    assert parse_answer("급여이체", "네 이체할 거예요") is True
    assert parse_answer("급여이체", "아니요 안 할 것 같아요") is False
    assert parse_answer("급여이체", "잘 모르겠어요") is False  # 애매 -> conservative_fallback
    print("OK")

    if "--ai" in sys.argv:
        print()
        print("=== AI 경로 점검 ('기타' 질문 생성 + 애매한 답변 파싱) ===")
        etc_condition = {
            "condition_type": "기타",
            "evidence_text": "주택청약종합저축 보유 시 우대",
        }
        q = build_question(etc_condition)
        print(f"'기타' 질문 생성 결과: {q}")
        ambiguous = parse_answer("기타", "음... 있었던 것 같기도 하고 잘은 모르겠는데요")
        print(f"애매한 자유텍스트 파싱 결과(항상 False여야 함): {ambiguous}")
        assert ambiguous is False
