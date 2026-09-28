"""
Step3 미니플로우① — 후보 상품 풀의 미해결 조건(condition)에 대해 질문을 만들고,
사용자의 자유텍스트 답변을 구조화된 값(boolean/숫자)으로 해석하는 모듈.
(claude/Step3_후보풀_미니플로우1_스펙_20260923.md 2장의 인터페이스를 코드로 옮기는 자리)

AI 개입 범위 (PR #11 리뷰, junhee-ko 코멘트에 대한 답):
- 8~10개 고정 condition_type은 이 모듈이 결정론적 템플릿으로 질문을 만든다. AI 호출 없음.
- condition_type == "기타"인 조건만 evidence_text 원문을 보고 AI가 질문 문장을 생성한다.
- 사용자의 자유텍스트 답변은 AI를 한 번 호출해 기대 타입(boolean/숫자)으로 파싱한다.
- 파싱이 애매하거나("잘 모르겠어요" 포함) 실패하면 반드시 "조건 미충족"으로 보수적으로
  처리한다 — 계산값을 부풀리지 않는 방향. AI의 해석 결과를 곧이곧대로 신뢰하지 않는다.
- evidence_text 원문(공식 공시 텍스트) 자체의 정확성은 이 모듈의 검증 대상이 아니다 —
  소스 데이터의 정확성은 전제로 둔다(BE가 여기까지 재검증하지 않아도 됨).

실제 질문 생성/파싱 로직(build_question, parse_answer 내부)은 아직 미구현(TODO).
지금 이 파일의 목적은 "애매하면 항상 미충족" 규칙을 conservative_fallback() 한 곳에
강제해두는 것 — 나중에 실제 로직을 채울 때도 애매한 경로는 반드시 이 함수를 거치게 할 것.
"""

from typing import Optional


FIXED_TEMPLATES = {
    # TODO: 8~10개 고정 카테고리 질문 템플릿 채우기
    # "급여이체": "이 은행으로 급여를 이체하실 건가요?",
}


def conservative_fallback() -> bool:
    """애매하거나 파싱 실패 시 항상 이 값을 반환 — 조건 미충족(False)으로 취급.

    "AI 해석이 불확실하면 계산값을 부풀리지 않는다"는 규칙을 한 곳에 강제하기 위한 함수.
    실제 파싱 로직을 나중에 채우더라도, 실패/애매 경로는 항상 이 함수를 거칠 것.
    """
    return False


def build_question(condition: dict) -> str:
    """condition_type이 고정 카테고리면 템플릿, "기타"면 AI 질문 생성(미구현)."""
    condition_type = condition["condition_type"]
    if condition_type in FIXED_TEMPLATES:
        return FIXED_TEMPLATES[condition_type]
    raise NotImplementedError("'기타' 조건 질문 생성(AI 호출)은 아직 구현 전 - TODO")


def parse_answer(condition_type: str, raw_answer: str) -> Optional[bool]:
    """자유텍스트 답변을 boolean으로 해석한다 (AI 호출 자리, 아직 미구현).

    실제 AI 파싱을 구현하기 전까지는 항상 conservative_fallback()만 반환한다 —
    "미구현 상태에서 잘못 True를 반환하는 일"이 절대 없도록.
    """
    return conservative_fallback()
