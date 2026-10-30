"""
Summary(호출 B) — [패키지 모듈] BE에서는 `from ktc4_ai.summary import generate_summary`로 쓴다.
(로컬 품질 확인용 실행 스크립트는 scripts/summary_prompt.py)

계산 엔진이 만든 포트폴리오(4개 티어: 단순형/균형형/최대형/안정형)와 비교 기준선(단일형)을
보고, 티어별로 "왜 이 조합을 추천하는지" 자연어 설명(reason)을 만드는 AI 호출.

[티어 정의 - 2026-10-13 확정]
  단순형 : 사용자가 이미 충족하는 조건만으로 받을 수 있는 최대 실수령액.
           새 기관 가입 없음. (신협·새마을금고는 조합/금고마다 따로 가입해야 해서
           항상 '신규 가입'으로 보므로 단순형에는 들어가지 않는다)
  균형형 : 약간의 행동 변화로 받을 수 있는 최대 실수령액.
           새 기관 가입 최대 1곳 + 일회성 조건(마케팅동의·비대면가입 등) + 자동이체까지.
  최대형 : 모든 우대조건 달성을 가정한 최대 실수령액(카드실적·급여이체·보험/공제 가입 포함).
           보험/공제 가입 시 보험료는 실수령액에 반영되지 않으므로 "별도"라고 반드시 안내.
  안정형 : 1금융권 상품만으로 구성(우대조건은 반영). "1금융권 선호" 사용자용.
           예금자보호는 저축은행·상호금융도 1억원으로 같으므로 "더 안전하다"고 말하지 않는다.
           단순형과는 비교하지 않는다(1금융만 쓰므로 단순형보다 낮을 수 있음).
  단일형 : 주거래 은행 상품 중 실효금리 1위 하나에 전액(예금자보호 1억 원칙 미적용).
           추천안이 아니라 비교 기준선 -> reason을 만들지 않고, 각 안의
           "단일형 대비 +X원"(extra_vs_baseline)으로만 쓴다.
  (티어별 상품 구성/계산은 계산 엔진 책임. 이 모듈은 결과를 설명만 한다)

BE 스키마(backend/app/schemas/portfolio.py)를 따름:
  PortfolioProductOut: institution_code(*), institution_name, product_name,
                        term_months, interest_rate, allocated_amount, after_tax_interest,
                        applied_conditions(*)
  PortfolioOptionOut:  tier, products, after_tax_total, tax_saving_won(*),
                        over_comprehensive_tax(*), reason  <- reason이 이 모듈의 산출물
  (*) 2026-10 현재 BE 응답에 아직 없는 필드. BE/엔진에 추가 요청 필요.
      없으면 해당 판정값이 None/빈 목록이 되고, AI도 그 부분은 언급하지 않는다.

  applied_conditions 형태(상품마다, 엔진이 이 상품 금리에 반영했다고 가정한 우대조건):
    [{"condition_type": "자동이체", "bonus_rate": 0.2,
      "threshold_value": 30, "threshold_unit": "만원",
      "already_met": false}, ...]
    already_met=true  : 사용자가 이미 충족(Step3 답변 기준) -> 할 일 아님
    already_met=false/None : 새로 해야 하는 일 -> required_actions에 들어감(보수적)

  baseline(단일형) 형태:
    {"institution_name": "국민은행", "product_name": "...",
     "after_tax_total": 412000, "exceeds_protection": false}

AI 개입 범위(중요): 숫자(after_tax_total/interest_rate 등)를 다시 계산하거나 바꾸지
않는다. "단일형보다 얼마 더 받는지", "해야 할 일 목록" 같은 파생값도 AI가 추측하지
않도록 전부 이 파이썬 코드에서 미리 계산해서 넘긴다(_enrich_options). 저율과세 절감액,
금융소득종합과세 초과 여부는 엔진이 계산한 값을 그대로 통과시킨다.

NFR-04("LLM 호출 지점이 정확히 3곳"): (A) condition_qa.build_etc_questions, (B) condition_qa.
parse_answer, (C) 이 Summary. 4개 티어 reason을 반드시 한 번의 호출로 묶어서 만든다.
"""
import json
import re
import sys
import time
from typing import Optional

# 상대 import: 이 폴더(src/)는 스크립트에서는 `src`로, 패키지로 설치하면 `ktc4_ai`로
# 불린다. 절대경로로 쓰면 설치된 패키지에서 깨지므로 반드시 상대 import.
from .config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from .schemas.summary import SummaryResult

SIMPLE_TIER = "단순형"
BALANCED_TIER = "균형형"
MAX_TIER = "최대형"
STABLE_TIER = "안정형"
TIERS = (SIMPLE_TIER, BALANCED_TIER, MAX_TIER, STABLE_TIER)
# 단순형과 비교(extra_vs_simple, rate_gap_vs_simple, best_extra_elsewhere)하는 티어.
# 안정형은 1금융만 쓰는 다른 축의 안이라 단순형과 비교하지 않는다(2026-10-13 결정).
COMPARE_WITH_SIMPLE_TIERS = (BALANCED_TIER, MAX_TIER)
# AI 응답 최대 길이(토큰). 4개 티어 reason(각 4~6문장) + JSON 껍데기가 들어갈 만큼 넉넉히.
# 스트리밍 호출이라 프록시의 non-streaming 2,000 토큰 제한을 받지 않는다(_call_streaming 참고).
SUMMARY_MAX_TOKENS = 4000

# 신협·새마을금고는 조합/금고(지점)마다 별개 법인이라 출자금을 내고 조합원(회원)으로
# 따로 가입해야 한다. 사용자가 "신협"/"새마을금고"를 보유은행으로 골라도 추천된 그
# 조합·금고에 계좌가 있다는 보장이 없으므로, 보유 여부와 상관없이 항상 "신규 가입
# 필요"로 본다 (2026-10 팀 결정).
# 코드 접두사 (ai/output/erd/institution.jsonl 기준): 신협 "CU-"(847곳), 새마을금고 "KFCC-"(1,039곳)
ALWAYS_NEW_CODE_PREFIXES = ("CU-", "KFCC-")

# 우대조건(condition_type) -> "해야 할 일" 문구. {inst}=기관명, {th}=" (월 30만원 이상)" 같은 기준.
# 신규고객은 new_banks(새로 가입할 곳)로 이미 안내되고, 연령조건은 행동이 아니라 자격이라 제외.
ACTION_TEMPLATES = {
    "급여이체": "{inst} 계좌로 급여 받기{th}",
    "자동이체": "{inst} 계좌로 자동이체 등록{th}",
    "카드실적": "{inst} 카드 실적 채우기{th}",
    "마케팅동의": "{inst} 마케팅 정보 수신 동의",
    "공과금이체": "{inst} 계좌로 공과금 자동이체{th}",
    "연금수령": "{inst} 계좌로 연금 수령",
    "비대면가입": "{inst} 상품을 앱(비대면)으로 가입",
    "공제가입": "{inst} 공제(보험) 상품 가입",
    "주거래은행": "{inst} 계좌를 주거래로 사용(급여·카드·자동이체 등)",
    "기타": "{inst} 기타 우대조건 충족",
}
SKIP_ACTION_TYPES = ("신규고객", "연령조건")
# 보험료가 별도로 드는 조건 -> "보험료는 실수령액에 미반영" 안내 대상
INSURANCE_CONDITION_TYPES = ("공제가입",)


def _is_always_new(code: Optional[str]) -> bool:
    return bool(code) and code.startswith(ALWAYS_NEW_CODE_PREFIXES)


def _threshold_text(cond: dict) -> str:
    value, unit = cond.get("threshold_value"), cond.get("threshold_unit")
    if value is None or not unit:
        return ""
    value_str = f"{value:,}" if isinstance(value, int) else str(value)
    return f" (월 {value_str}{unit} 이상)"


def _actions_for_product(product: dict) -> tuple:
    """상품 하나에 적용된 우대조건 중 '아직 안 한 것'을 할 일 문구로 바꾼다.
    반환: (할 일 문구 목록, 보험/공제 조건 포함 여부)"""
    inst = product.get("institution_name", "")
    actions, has_insurance = [], False
    for cond in product.get("applied_conditions") or []:
        ctype = cond.get("condition_type") or "기타"
        if ctype in INSURANCE_CONDITION_TYPES:
            has_insurance = True
        if cond.get("already_met") is True or ctype in SKIP_ACTION_TYPES:
            continue
        template = ACTION_TEMPLATES.get(ctype, ACTION_TEMPLATES["기타"])
        actions.append(template.format(inst=inst, th=_threshold_text(cond)))
    return actions, has_insurance


_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        if not OPENAI_API_KEY or not OPENAI_BASE_URL:
            raise RuntimeError(
                "OPENAI_API_KEY / OPENAI_BASE_URL이 .env에 설정 안 돼 있음 - Summary 호출을 "
                "쓰려면 필요함."
            )
        _client = OpenAI(api_key=OPENAI_API_KEY, base_url=f"{OPENAI_BASE_URL}/v1")
    return _client


SYSTEM_PROMPT = (
    "너는 예적금 포트폴리오 추천 서비스의 설명 문구를 쓰는 어시스턴트야. "
    "입력은 사용자 정보(user), 비교 기준선(baseline), 계산 엔진이 이미 계산을 끝낸 포트폴리오 "
    "4개 안(options)이야. 각 안마다 사용자가 '이 추천은 믿을 만하다'고 느낄 수 있도록, "
    "구체적인 근거를 들어 왜 이 조합을 추천하는지 설명하는 글(reason)을 만들어줘. "
    "baseline에 대한 글은 만들지 마.\n\n"
    "안의 의미:\n"
    "- baseline(단일형): 주거래 은행 상품 하나에 전액을 넣었을 때. 비교 기준으로만 써.\n"
    "- 단순형: 이미 충족하는 조건만으로 받을 수 있는 최대 이자. 지금 그대로 바로 실행 가능.\n"
    "- 균형형: 새 기관 1곳 가입, 자동이체 같은 가벼운 행동 변화로 더 받는 안.\n"
    "- 최대형: 카드 실적, 급여이체, 보험 가입 등 모든 우대조건을 충족한다고 가정한 최대 이자.\n"
    "- 안정형: 1금융권 상품만으로 구성한 안. 1금융권을 선호하는 사람을 위한 안.\n\n"
    "입력 필드 설명:\n"
    "- baseline.after_tax_total / institution_name / product_name: 단일형 결과.\n"
    "- baseline.exceeds_protection: true면 주거래 은행 한 곳에 전액을 넣으면 1억원 초과분이 "
    "예금자보호를 받지 못한다는 뜻.\n"
    "- products[].is_existing_bank: true=이미 거래 중인 은행, false=새로 가입해야 하는 은행, "
    "null=알 수 없음(이 경우 기존/신규 여부를 절대 언급하지 마).\n"
    "- products[].is_main_bank: true면 사용자의 주거래은행 상품.\n"
    "- products[].requires_membership: true면 신협·새마을금고 상품이라 조합원(회원) 가입"
    "(출자금 납입)이 필요해. 출자금 액수는 주어지지 않았으니 금액은 말하지 마.\n"
    "- products[].rate_gap_vs_simple: 단순형에서 가장 높은 금리보다 몇 %p 높은지"
    "(null이거나 0 이하면 금리 차이는 언급하지 마).\n"
    "- new_banks: 이 안을 실행하려면 새로 가입해야 하는 기관 이름 목록.\n"
    "- required_actions: 이 안의 금리를 받으려면 새로 해야 하는 일 목록(문구 그대로 써).\n"
    "- has_insurance_condition: true면 보험·공제 가입 조건이 포함돼 있고, 보험료는 이자에 "
    "반영되지 않았음.\n"
    "- extra_vs_baseline: 단일형(baseline)보다 세후 이자를 몇 원 더 받는지. "
    "same_as_baseline이 true면 단일형과 결과가 같다는 뜻.\n"
    "- extra_vs_simple: (균형형·최대형에만) 단순형보다 세후 이자를 몇 원 더 받는지.\n"
    "- best_extra_elsewhere: (단순형에만) 균형형·최대형 중 최대 몇 원 더 받을 수 있는지와 "
    "그 안의 이름(best_extra_tier).\n"
    "- tax_saving_won: 상호금융 저율과세로 줄어든 세금(원). null이면 언급하지 마.\n"
    "- over_comprehensive_tax: true면 이자가 연 2,000만원을 넘어 금융소득종합과세 대상이 될 수 "
    "있다는 뜻.\n"
    "- same_term: true면 모든 상품의 만기(term_months)가 같아서 한 번에 찾을 수 있음.\n\n"
    "글의 구성 (반드시 3문단으로 나누고 문단 사이에는 줄바꿈 두 번(\\n\\n)을 넣어. "
    "한 문단으로 이어 쓰지 마. 전체 4~6문장, 존댓말):\n"
    "1문단 - 무엇을 어떻게 담았는지: 각 상품을 왜 골랐는지(금리, rate_gap_vs_simple, "
    "기존 거래 은행인지) 와 금액을 어떻게 나눴는지(allocated_amount). 만기가 같으면 함께 "
    "찾을 수 있다는 점도.\n"
    "2문단 - 결과 숫자: 세후 이자 합계(after_tax_total)와, 주거래 은행 상품 하나에 넣었을 때보다 "
    "extra_vs_baseline원 더 받는다는 점(same_as_baseline이면 '주거래 은행 상품 하나로도 같은 "
    "결과'라고). 균형형·최대형은 extra_vs_simple(단순형 대비)도. tax_saving_won이 있으면 "
    "그중 저율과세로 줄어든 세금이 얼마인지.\n"
    "3문단 - 실행할 때 알아둘 점:\n"
    "  · 단순형: '추가 가입 없이 지금 계좌로 바로 가능'하다는 점과, best_extra_elsewhere가 있으면 "
    "'우대조건을 더 챙기면 {best_extra_tier}에서 최대 그만큼 더 받을 수 있다'는 안내('약간', '조금만' 같은 표현은 쓰지 마 - 최대형은 챙길 조건이 많음). "
    "baseline.exceeds_protection이 true면 '주거래 은행 한 곳에 전부 넣으면 1억원 초과분은 "
    "예금자보호를 받지 못한다'는 점도.\n"
    "  · 균형형·최대형: new_banks 가입과 required_actions를 그대로 나열. requires_membership "
    "상품이 있으면 조합원 가입 필요. has_insurance_condition이 true면 '보험료는 이자에 반영되지 "
    "않았다'는 점을 반드시 써.\n"
    "  · 안정형: 1금융권 상품만으로 구성했다는 점과 required_actions(있으면).\n"
    "  · 모든 안: over_comprehensive_tax가 true면 금융소득종합과세 대상이 될 수 있다는 점.\n\n"
    "반드시 지켜야 할 규칙:\n"
    "- 숫자는 절대 다시 계산하거나 바꾸지 마. 주어진 값을 그대로 인용만 해. 더하기·빼기·"
    "비율 계산도 하지 마. 차이는 extra_vs_baseline, extra_vs_simple, rate_gap_vs_simple, "
    "best_extra_elsewhere, tax_saving_won 값만 써.\n"
    "- 금액은 천 단위 콤마와 '원'을 붙여(예: 350,000원, 5,000,000원). 금리는 주어진 숫자에 %, "
    "금리 차이는 %p를 붙여.\n"
    "- 예금자보호, 저율과세, 종합과세, 우대조건은 위 필드 값이 있을 때만 언급해. 입력에 없는 "
    "정보(중도해지 이율, 출자금 액수, 보험료 액수, 다른 상품, 시장 전망 등)는 언급하지 마.\n"
    "- 안정형을 단순형과 비교하지 마. 안정형이 다른 안보다 안전하다거나 예금자보호가 더 낫다고 "
    "말하지 마(저축은행·상호금융도 1억원까지 보호됨). '1금융권을 선호하는 분을 위한 안'으로만 "
    "설명해.\n"
    "- is_existing_bank와 new_banks에 근거해서만 '기존 계좌로 가능', '새로 가입 필요'를 말해. "
    "단순형이라도 new_banks나 required_actions가 비어 있지 않으면 '추가 가입 없이'라고 쓰지 마.\n"
    "- 네 안이 비슷하게 읽히지 않게: 단순형은 바로 실행 가능함, 균형형은 적은 행동 변화로 "
    "얻는 이득, 최대형은 최대 수익과 그만큼 챙겨야 할 조건, 안정형은 1금융권 구성을 중심으로.\n"
    "- 과장 표현(무조건, 확실히, 최고의 등)은 쓰지 마.\n\n"
    "반드시 아래 JSON 형식으로만 응답해. 코드블록(```) 없이, 설명 문장 없이, "
    "순수 JSON 객체 하나만 출력해. options에 있는 안만 넣어:\n"
    '{"reasons": [{"tier": "단순형", "reason": "1문단\\n\\n2문단\\n\\n3문단"}, '
    '{"tier": "균형형", "reason": "..."}, {"tier": "최대형", "reason": "..."}, '
    '{"tier": "안정형", "reason": "..."}]}'
)

CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_code_fence(text: str) -> str:
    return CODE_FENCE_RE.sub("", text.strip()).strip()


def _find_valid_result(node, depth=0) -> Optional[SummaryResult]:
    """extract_conditions_ai.py의 _find_valid_result와 같은 방식 - 이 API가 가끔
    결과를 이중으로 감싸서 주는 경우까지 포함해서 재귀적으로 찾는다."""
    if depth > 5:
        return None
    if isinstance(node, dict):
        try:
            return SummaryResult(**node)
        except Exception:
            pass
        for value in node.values():
            candidate = value
            if isinstance(candidate, str):
                try:
                    candidate = json.loads(candidate)
                except Exception:
                    continue
            result = _find_valid_result(candidate, depth + 1)
            if result:
                return result
    return None


def _call_streaming(client, payload: str) -> tuple:
    """AI를 stream=True로 호출해서 (전체 응답 문자열, finish_reason)을 돌려준다.

    왜 스트리밍인가: 이 API 프록시는 non-streaming 응답의 max_tokens를 2,000으로 제한한다
    (그 이상이면 400 에러, 기본값으로 두면 4개 티어 JSON이 중간에 잘림 - 2026-10-13 실제 발생).
    stream=True면 한도 없이 끝까지 받을 수 있다. 호출 횟수는 그대로 1번(NFR-04 유지)."""
    stream = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": payload},
        ],
        max_tokens=SUMMARY_MAX_TOKENS,
        stream=True,
    )
    parts, finish_reason = [], None
    for chunk in stream:
        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        if choice.delta is not None and choice.delta.content:
            parts.append(choice.delta.content)
        if choice.finish_reason:
            finish_reason = choice.finish_reason
    return "".join(parts), finish_reason


def _enrich_options(
    portfolio_options: list, user_context: Optional[dict], baseline: Optional[dict] = None
) -> list:
    """AI에 넘기기 전에, AI가 추측하면 안 되는 파생값을 코드로 미리 계산해서 붙인다.

    user_context 형태(없으면 None):
      {"main_bank_code": "BANK-0010927" | None,
       "held_bank_codes": ["BANK-0010927", "BANK-0015130", ...]}   # 보유(거래 중) 은행
    baseline: 단일형 결과(모듈 docstring 참고). 없으면 extra_vs_baseline=None.

    상품마다 붙이는 값:
      is_existing_bank    : 보유 은행 또는 주거래은행이면 True, 아니면 False,
                            institution_code나 user_context가 없으면 None(판정 불가)
      is_main_bank        : 주거래은행 상품이면 True
      requires_membership : 신협·새마을금고 상품이면 True - 조합원 가입(출자금 납입)이 필요해서
                            보유은행 목록과 상관없이 is_existing_bank=False로 고정
      rate_gap_vs_simple  : (균형형·최대형만) 단순형 상품 중 최고 금리 대비 몇 %p 높은지
    안(option)마다 붙이는 값:
      new_banks               : 새로 가입해야 하는 기관 이름 목록(중복 제거)
      required_actions        : applied_conditions 중 아직 안 한 우대조건 -> 할 일 문구(중복 제거)
      has_insurance_condition : 보험/공제 가입 조건 포함 여부
      extra_vs_baseline       : 단일형 대비 세후 이자 증가분(원). baseline 없으면 None
      same_as_baseline        : extra_vs_baseline == 0
      extra_vs_simple         : (균형형·최대형만) 단순형 대비 세후 이자 증가분(원)
      tax_saving_won          : 엔진 값 그대로(정수가 아니면 None)
      over_comprehensive_tax  : 엔진 값 그대로(True일 때만 True)
      same_term               : 모든 상품 만기가 같으면 True
      best_extra_elsewhere    : (단순형에만) 균형형·최대형 중 extra_vs_simple 최댓값과 그 안 이름
    FE의 vsSingleDiff(=extra_vs_baseline), newAccountCount(=len(new_banks))와 같은 값이라
    BE가 응답 필드를 채울 때도 이 함수 결과를 그대로 쓸 수 있다.
    """
    main_code = (user_context or {}).get("main_bank_code")
    held = set((user_context or {}).get("held_bank_codes") or [])
    if main_code:
        held.add(main_code)
    can_judge = user_context is not None

    baseline_total = (baseline or {}).get("after_tax_total")
    if not isinstance(baseline_total, int):
        baseline_total = None

    simple = next((o for o in portfolio_options if o.get("tier") == SIMPLE_TIER), None)
    simple_total = simple.get("after_tax_total") if simple else None
    simple_rates = [
        p["interest_rate"]
        for p in (simple or {}).get("products", [])
        if isinstance(p.get("interest_rate"), (int, float))
    ]
    simple_best_rate = max(simple_rates) if simple_rates else None

    enriched = []
    for opt in portfolio_options:
        tier = opt.get("tier")
        compare_simple = tier in COMPARE_WITH_SIMPLE_TIERS
        products = []
        new_banks: list = []
        actions: list = []
        has_insurance = False
        for p in opt.get("products", []):
            code = p.get("institution_code")
            requires_membership = _is_always_new(code)
            if requires_membership:
                # 신협·새마을금고: user_context가 없어도 "신규 가입"인 건 확실하므로 False로 확정
                is_existing, is_main = False, False
            elif can_judge and code:
                is_existing = code in held
                is_main = bool(main_code) and code == main_code
            else:
                is_existing, is_main = None, None
            if is_existing is False and p.get("institution_name") not in new_banks:
                new_banks.append(p.get("institution_name"))

            p_actions, p_insurance = _actions_for_product(p)
            for a in p_actions:
                if a not in actions:
                    actions.append(a)
            has_insurance = has_insurance or p_insurance

            rate = p.get("interest_rate")
            rate_gap = None
            if compare_simple and simple_best_rate is not None and isinstance(rate, (int, float)):
                rate_gap = round(rate - simple_best_rate, 2)

            # applied_conditions는 actions로 이미 요약했으므로 AI 입력에서는 뺀다(토큰 절약,
            # AI가 원본 조건을 보고 문구를 따로 지어내는 것 방지)
            product_out = {k: v for k, v in p.items() if k != "applied_conditions"}
            products.append(
                {
                    **product_out,
                    "is_existing_bank": is_existing,
                    "is_main_bank": is_main,
                    "requires_membership": requires_membership,
                    "rate_gap_vs_simple": rate_gap,
                }
            )

        total = opt.get("after_tax_total")
        extra_simple = None
        if compare_simple and isinstance(simple_total, int) and isinstance(total, int):
            extra_simple = total - simple_total
        extra_base = None
        if baseline_total is not None and isinstance(total, int):
            extra_base = total - baseline_total
        tax_saving = opt.get("tax_saving_won")
        terms = {p.get("term_months") for p in products}

        enriched.append(
            {
                "tier": tier,
                "products": products,
                "after_tax_total": total,
                "new_banks": new_banks,
                "required_actions": actions,
                "has_insurance_condition": has_insurance,
                "extra_vs_baseline": extra_base,
                "same_as_baseline": extra_base == 0,
                "extra_vs_simple": extra_simple,
                "tax_saving_won": tax_saving if isinstance(tax_saving, int) and tax_saving > 0 else None,
                "over_comprehensive_tax": opt.get("over_comprehensive_tax") is True,
                "same_term": len(products) > 1 and len(terms) == 1,
            }
        )

    # 단순형에 "우대조건을 더 챙기면 최대 얼마 더"를 붙인다 (균형형·최대형만 대상, 안정형 제외)
    others = [
        o for o in enriched
        if o["tier"] in COMPARE_WITH_SIMPLE_TIERS and isinstance(o["extra_vs_simple"], int)
    ]
    best = max(others, key=lambda o: o["extra_vs_simple"], default=None)
    for o in enriched:
        if o["tier"] == SIMPLE_TIER and best and best["extra_vs_simple"] > 0:
            o["best_extra_elsewhere"] = best["extra_vs_simple"]
            o["best_extra_tier"] = best["tier"]
    return enriched


def _fallback_reason(option: dict, baseline: Optional[dict] = None) -> str:
    """AI 호출이 끝까지 실패했을 때 쓰는 기본 문구. _enrich_options를 거친 option을
    받는다. 숫자를 지어내지 않고 계산된 값만으로, AI 버전과 같은 3문단 구성으로 만든다."""
    tier = option.get("tier", "")
    products = option.get("products", [])
    total = option.get("after_tax_total")
    total_str = f"{total:,}원" if isinstance(total, int) else "?"
    new_banks = option.get("new_banks") or []
    actions = option.get("required_actions") or []
    extra_base = option.get("extra_vs_baseline")
    extra_simple = option.get("extra_vs_simple")
    tax_saving = option.get("tax_saving_won")
    all_existing = bool(products) and all(p.get("is_existing_bank") is True for p in products)

    def _item(p):
        name = f'{p.get("institution_name", "")} {p.get("product_name", "")}'.strip()
        rate = p.get("interest_rate")
        amount = p.get("allocated_amount")
        detail = []
        if isinstance(rate, (int, float)):
            detail.append(f"{rate}%")
        if isinstance(amount, int):
            detail.append(f"{amount:,}원")
        return f"{name}({', '.join(detail)})" if detail else name

    # 1문단: 구성
    items = ", ".join(_item(p) for p in products[:3])
    para1 = f"{items}에 담은 조합입니다."
    if tier == STABLE_TIER:
        para1 = f"1금융권 상품만으로 {items}에 담은 조합입니다."
    if option.get("same_term"):
        para1 += " 모든 상품의 만기가 같아 한 번에 찾을 수 있습니다."

    # 2문단: 숫자
    para2 = f"세후 이자는 {total_str}입니다."
    if option.get("same_as_baseline"):
        para2 = f"세후 이자는 {total_str}으로, 주거래 은행 상품 하나에 넣었을 때와 같습니다."
    elif isinstance(extra_base, int) and extra_base > 0:
        para2 = f"세후 이자는 {total_str}으로, 주거래 은행 상품 하나에 넣었을 때보다 {extra_base:,}원을 더 받습니다."
    if isinstance(extra_simple, int) and extra_simple > 0:
        para2 += f" 단순형보다는 {extra_simple:,}원 많습니다."
    if isinstance(tax_saving, int) and tax_saving > 0:
        para2 += f" 이 중 상호금융 저율과세로 줄어든 세금은 {tax_saving:,}원입니다."

    # 3문단: 실행할 때 알아둘 점
    notes = []
    if tier == SIMPLE_TIER:
        if all_existing and not actions:
            notes.append("추가 가입 없이 지금 거래 중인 계좌로 바로 시작할 수 있습니다.")
        if option.get("best_extra_elsewhere"):
            notes.append(
                f"우대조건을 더 챙기면 {option['best_extra_tier']}에서 최대 "
                f"{option['best_extra_elsewhere']:,}원을 더 받을 수 있습니다."
            )
        if (baseline or {}).get("exceeds_protection") is True:
            notes.append("주거래 은행 한 곳에 전부 넣으면 1억원 초과분은 예금자보호를 받지 못합니다.")
    else:
        if tier == STABLE_TIER:
            notes.append("1금융권 상품을 선호하는 분을 위한 안입니다.")
        if new_banks:
            notes.append(f"{', '.join(new_banks)}에 새로 가입해야 합니다.")
        if actions:
            notes.append(f"우대금리를 받으려면 다음을 챙겨야 합니다: {', '.join(actions)}.")
        if any(p.get("requires_membership") for p in products):
            notes.append("신협·새마을금고 상품은 조합원 가입(출자금 납입)이 필요합니다.")
        if option.get("has_insurance_condition"):
            notes.append("보험·공제 가입 조건의 보험료는 이자에 반영되지 않았습니다.")
    if option.get("over_comprehensive_tax"):
        notes.append("이자가 연 2,000만원을 넘으면 금융소득종합과세 대상이 될 수 있습니다.")

    return "\n\n".join(x for x in [para1, para2, " ".join(notes)] if x)


def generate_summary(
    portfolio_options: list,
    user_context: Optional[dict] = None,
    baseline: Optional[dict] = None,
    retries: int = 3,
) -> dict:
    """포트폴리오 티어들(단순형/균형형/최대형/안정형)을 받아서 {tier_이름: reason_문자열}을 반환한다.

    portfolio_options: PortfolioOptionOut과 같은 shape(reason은 없어도 됨).
    user_context: 위 _enrich_options 설명 참고. 없으면 기존/신규 은행 구분 없이 설명한다.
    baseline: 단일형 결과. reason은 만들지 않고 비교(extra_vs_baseline)에만 쓴다.

    AI 호출이 끝까지 실패하면 예외를 던지지 않고 _fallback_reason()으로 채운다 -
    Summary 실패가 전체 포트폴리오 응답을 막으면 안 되므로."""
    enriched = _enrich_options(portfolio_options, user_context, baseline)
    payload = json.dumps(
        {"user": user_context, "baseline": baseline, "options": enriched}, ensure_ascii=False
    )
    tiers_in_input = {opt["tier"] for opt in enriched}

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            client = _get_client()
            content, finish_reason = _call_streaming(client, payload)
            if finish_reason == "length":
                raise ValueError(
                    f"응답이 출력 한도에서 잘림(finish_reason=length, {len(content)}자). "
                    "SUMMARY_MAX_TOKENS를 늘려야 함."
                )
            node = json.loads(_strip_code_fence(content))
            parsed = _find_valid_result(node)
            if parsed is None:
                raise ValueError(f"SummaryResult로 해석 안 됨. 원문 응답: {content[:300]}")
            # 입력에 없는 티어(예: AI가 단일형 글을 만든 경우)는 버린다
            reasons = {r.tier: r.reason for r in parsed.reasons if r.tier in tiers_in_input}
            # AI가 티어를 하나 빼먹었으면 그 티어만 fallback으로 채운다
            for opt in enriched:
                reasons.setdefault(opt["tier"], _fallback_reason(opt, baseline))
            return reasons
        except Exception as e:  # noqa: BLE001
            last_error = e
            if attempt < retries:
                time.sleep(2**attempt)

    print(f"[Summary] AI 호출 실패 - fallback 사용: {last_error!r}", file=sys.stderr)
    return {opt["tier"]: _fallback_reason(opt, baseline) for opt in enriched}