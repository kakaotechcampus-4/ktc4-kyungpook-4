"""
챗봇 '기타' 우대조건 질문 생성 + 답변 해석 — [패키지 모듈]
BE에서는 `from ktc4_ai.condition_qa import build_etc_questions, parse_answer`로 쓴다.

[범위 - 2026-10-28 결정]
- 챗봇은 '기타' 우대조건만 묻는다. 급여이체·자동이체 등 고정 조건은 STEP2 입력 폼이,
  조합원 여부는 FE STEP3 화면이 이미 묻고 있다.
- 묻는 대상은 "추천 결과에 들어간 상품"의 '기타' 조건뿐이다(A안). 어떤 조건을 넘길지는
  BE가 정하고, 이 모듈은 받은 조건 목록만 처리한다.
- 원문(evidence_text)이 같은 조건은 질문 1개로 묶고, 그 질문의 답을 묶인 조건 전부에
  적용한다(condition_ids). 개수 상한은 두지 않는다.

[AI 신뢰 경계 - 기존 scripts/condition_qa.py(삭제)에서 옮김]
- 질문 생성: AI가 질문과 함께 근거 문구(grounding_quote)를 내고, 그 문구가 원문 안에
  실제로 있는지 코드에서 대조한다. 없거나 호출이 실패하면 원문을 그대로 보여주는
  안전한 질문으로 대체한다.
- 답변 해석: 짧은 정답형 답변(네/아니요 등)과 정확히 일치할 때만 AI 없이 판정하고,
  나머지는 AI가 confidence와 함께
  판정한다. confidence가 high가 아니거나 실패하면 conservative_fallback()(=미충족)이다.
  "애매하면 항상 미충족" - 계산값을 부풀리지 않는다.

NFR-04("LLM 호출 지점이 정확히 3곳"): (A) _build_question_ai, (B) _parse_answer_ai,
(C) summary.generate_summary. 새 호출 지점은 추가하지 않았다.
"""
import json
import re
from typing import Optional

# 상대 import: 스크립트에서는 `src`, 패키지로 설치하면 `ktc4_ai`로 불리므로 반드시 상대 import.
from .config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

ETC_TYPE = "기타"

_client = None


def _get_client():
    """AI 호출이 실제로 필요할 때만 클라이언트를 만든다(키 없이도 import는 되게)."""
    global _client
    if _client is None:
        from openai import OpenAI

        if not OPENAI_API_KEY or not OPENAI_BASE_URL:
            raise RuntimeError("OPENAI_API_KEY / OPENAI_BASE_URL이 .env에 설정 안 돼 있음")
        _client = OpenAI(api_key=OPENAI_API_KEY, base_url=f"{OPENAI_BASE_URL}/v1")
    return _client


CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_code_fence(text: str) -> str:
    return CODE_FENCE_RE.sub("", text.strip()).strip()


def _normalize(s: str) -> str:
    """공백·줄바꿈 차이를 무시하고 비교하기 위한 정규화."""
    return re.sub(r"\s+", "", s or "")


# ---------------------------------------------------------------------------
# 1) '기타' 조건 묶기 (AI 호출 없음)
# ---------------------------------------------------------------------------
def group_etc_conditions(conditions: list) -> list:
    """'기타' 조건 중 우대폭(rate_bonus)이 있는 것만 골라, 원문이 같은 것끼리 묶는다.

    conditions: [{"condition_id", "condition_type", "rate_bonus", "evidence_text"}, ...]
                (BE의 ProductCondition 필드명 그대로)
    반환: [{"evidence_text": 원문, "condition_ids": [묶인 조건 ID들]}, ...]  - 처음 나온 순서 유지
    원문이 비어 있는 조건은 무엇을 물어볼지 알 수 없어서 뺀다."""
    groups: dict = {}
    for cond in conditions:
        if cond.get("condition_type") != ETC_TYPE or cond.get("rate_bonus") is None:
            continue
        text = (cond.get("evidence_text") or "").strip()
        if not text:
            continue
        key = _normalize(text)
        if key not in groups:
            groups[key] = {"evidence_text": text, "condition_ids": []}
        if cond["condition_id"] not in groups[key]["condition_ids"]:
            groups[key]["condition_ids"].append(cond["condition_id"])
    return list(groups.values())


# ---------------------------------------------------------------------------
# 2) 질문 생성 (호출 지점 A)
# ---------------------------------------------------------------------------
_QUESTION_GEN_PROMPT = (
    "너는 예적금 우대조건 안내 챗봇이야. 아래는 어떤 예적금 상품의 우대조건 설명 원문이야. "
    "이 조건을 사용자가 충족하는지 물어보는 자연스러운 질문 문장 하나를 만들어줘.\n"
    "규칙:\n"
    "- 예/아니오로 답할 수 있는 질문 형태로 만들어.\n"
    "- 원문에 없는 내용을 지어내지 마. 원문의 의미를 벗어나지 마.\n"
    "- grounding_quote: 이 질문을 만든 근거가 되는 원문 속 문구를 한 글자도 바꾸지 "
    "않고 그대로(띄어쓰기 포함) 옮겨 적어. 최소 10자 이상.\n\n"
    "반드시 아래 JSON 형식으로만 응답해. 코드블록(```) 없이, 설명 문장 없이, "
    "순수 JSON 객체 하나만 출력해:\n"
    '{"question": "질문 문장", "grounding_quote": "원문에서 그대로 가져온 문구"}'
)


def fallback_question(text: str) -> str:
    """AI 질문을 못 쓸 때의 안전한 질문 - 원문을 그대로 보여준다."""
    return f'다음 조건에 해당하시나요? "{text}"'


def _build_question_ai(text: str) -> str:
    """원문을 보고 AI가 질문을 만든다. grounding_quote가 원문에 없거나 실패하면 fallback."""
    fallback = fallback_question(text)
    try:
        res = _get_client().chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _QUESTION_GEN_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        parsed = json.loads(_strip_code_fence(res.choices[0].message.content or ""))
        question = (parsed.get("question") or "").strip()
        quote = (parsed.get("grounding_quote") or "").strip()
        if question and quote and _normalize(quote) in _normalize(text):
            return question
        return fallback  # 근거 문구가 원문에 없음 - AI가 지어냈을 가능성
    except Exception:
        return fallback


def build_etc_questions(conditions: list) -> list:
    """'기타' 조건 목록 -> 질문 목록. 원문이 같은 조건은 질문 1개로 묶는다.

    반환: [{"question": 질문 문장, "evidence_text": 원문, "condition_ids": [...]}, ...]
    BE는 사용자의 답을 condition_ids 각각에 같은 값으로 저장하면 된다."""
    return [
        {**group, "question": _build_question_ai(group["evidence_text"])}
        for group in group_etc_conditions(conditions)
    ]


# ---------------------------------------------------------------------------
# 3) 답변 해석 (호출 지점 B) - 애매하면 항상 미충족
# ---------------------------------------------------------------------------
# 키워드는 "답변 전체가 정확히 이 말일 때"만 쓴다. 문장 안에 들어 있는지로 판단하면
# "해당 안 돼요"('해당'), "예금 계좌 없어요"('예')처럼 반대로 판정되기 때문이다.
# 비교 전에 공백과 끝의 문장부호(. ! ? ~ ,)를 지우고 영문은 소문자로 바꾼다.
_YES_ANSWERS = {"네", "예", "응", "넵", "네네", "맞아요", "맞아", "그래요", "yes", "y"}
_NO_ANSWERS = {"아니요", "아니오", "아뇨", "아니", "아니에요", "no", "n"}
_UNSURE_ANSWERS = {"모르겠어요", "잘모르겠어요", "몰라요", "모름", "글쎄요"}
_TRAILING_PUNCT_RE = re.compile(r"[.!?~,]+$")

_ANSWER_PARSE_PROMPT = (
    "사용자의 자유 텍스트 답변을 해석해줘. "
    "'예/네/응/충족/해당함' 계열이면 result=true, "
    "'아니오/아니요/미충족/해당 안 됨' 계열이면 result=false, "
    "'모르겠다/잘 모르겠어요'거나 답변이 애매해서 예/아니오를 확정할 수 없으면 "
    "result=null. confidence는 그 판단이 얼마나 명확한지 - 애매한 표현이거나 "
    "문맥을 더 봐야 확신할 수 있으면 \"low\", 명백하면 \"high\".\n\n"
    "반드시 아래 JSON 형식으로만 응답해. 코드블록(```) 없이, 설명 문장 없이, "
    "순수 JSON 객체 하나만 출력해:\n"
    '{"result": true, "confidence": "high"}'
)


def conservative_fallback() -> bool:
    """애매하거나 실패하면 항상 이 값 - 조건 미충족(False)."""
    return False


def _quick_keyword_match(raw_answer: str) -> Optional[bool]:
    """짧은 정답형 답변만 AI 없이 판정. 목록과 정확히 같지 않으면 None(AI로 넘김)."""
    text = _TRAILING_PUNCT_RE.sub("", _normalize(raw_answer).lower())
    if text in _YES_ANSWERS:
        return True
    if text in _NO_ANSWERS:
        return False
    if text in _UNSURE_ANSWERS:
        return conservative_fallback()  # 모르겠다 = 미충족. AI를 부를 필요 없음
    return None


def _parse_answer_ai(raw_answer: str) -> Optional[bool]:
    """AI가 해석. confidence가 high가 아니거나 결과가 true/false가 아니면 None."""
    try:
        res = _get_client().chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _ANSWER_PARSE_PROMPT},
                {"role": "user", "content": raw_answer},
            ],
        )
        parsed = json.loads(_strip_code_fence(res.choices[0].message.content or ""))
        result = parsed.get("result")
        if result not in (True, False) or parsed.get("confidence") != "high":
            return None
        return result
    except Exception:
        return None


def parse_answer(raw_answer: str) -> bool:
    """자유텍스트 답변 -> True(충족)/False(미충족). 순서: 키워드 -> AI -> 보수적 처리."""
    quick = _quick_keyword_match(raw_answer)
    if quick is not None:
        return quick
    ai_result = _parse_answer_ai(raw_answer)
    if ai_result is not None:
        return ai_result
    return conservative_fallback()