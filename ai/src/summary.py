"""
Summary(호출 B) — [패키지 모듈] BE에서는 `from ktc4_ai.summary import generate_summary`로 쓴다.
(로컬 품질 확인용 실행 스크립트는 scripts/summary_prompt.py)

계산 엔진이 만든 포트폴리오(3개 티어: 단순형/균형형/최대형)를
보고, 티어별로 "왜 이 조합을 추천하는지" 자연어 설명(reason)을 만드는 AI 호출.

[티어 정의 - 2026-10 기획 변경]
  단순형 : 주거래은행 / 이미 거래 중인 은행(보유 계좌)만으로 받을 수 있는 최대 이자.
           (신협·새마을금고는 조합/금고마다 따로 가입해야 해서 항상 '신규 가입'으로 본다)
           새 계좌 개설·신규 가입 없이 바로 실행 가능한 안.
  균형형 : 새 은행 가입을 일부 허용해서 단순형보다 이자를 더 높인 안.
  최대형 : 신규 가입 부담과 상관없이 이자를 최대로 만든 안.
  (균형형/최대형을 정확히 어떤 기준으로 나눌지는 추후 결정 - 이 모듈은 계산
   엔진이 준 결과를 "이미 거래 중인 은행 vs 새로 가입할 은행" 관점으로 설명만 한다)

BE 스키마(backend/app/schemas/portfolio.py)를 따름:
  PortfolioProductOut: institution_code(*), institution_name, product_name,
                        term_months, interest_rate, allocated_amount, after_tax_interest
  PortfolioOptionOut:  tier, products, after_tax_total, reason  <- reason이 이 모듈의 산출물
  (*) institution_code는 2026-10 현재 BE 응답에 아직 없음. 데이터(product.institution_code)
      에는 있으므로 BE에 필드 추가 요청 필요. 없으면 "이미 거래하는 은행인지"를 판정할 수
      없어서 is_existing_bank=None(알 수 없음)으로 넘기고, AI도 그 부분은 언급하지 않는다.

AI 개입 범위(중요): 숫자(after_tax_total/interest_rate 등)를 다시 계산하거나 바꾸지
않는다. "이미 거래하는 은행인지", "단순형보다 얼마 더 받는지" 같은 파생값도 AI가 추측하지
않도록 전부 이 파이썬 코드에서 미리 계산해서 넘긴다(_enrich_options). AI는 주어진 값을
사람이 읽기 좋은 문장으로 옮기기만 한다.

NFR-04("LLM 호출 지점이 정확히 3곳"): (A) condition_qa.build_question, (B) condition_qa.
parse_answer, (C) 이 Summary. 3개 티어 reason을 반드시 한 번의 호출로 묶어서 만든다.
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

# 신협·새마을금고는 조합/금고(지점)마다 별개 법인이라 출자금을 내고 조합원(회원)으로
# 따로 가입해야 한다. 사용자가 "신협"/"새마을금고"를 보유은행으로 골라도 추천된 그
# 조합·금고에 계좌가 있다는 보장이 없으므로, 보유 여부와 상관없이 항상 "신규 가입
# 필요"로 본다 (2026-10 팀 결정).
# 코드 접두사 (ai/output/erd/institution.jsonl 기준): 신협 "CU-"(847곳), 새마을금고 "KFCC-"(1,039곳)
ALWAYS_NEW_CODE_PREFIXES = ("CU-", "KFCC-")


def _is_always_new(code: Optional[str]) -> bool:
    return bool(code) and code.startswith(ALWAYS_NEW_CODE_PREFIXES)

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
    "입력은 사용자 정보(user)와, 계산 엔진이 이미 계산을 끝낸 포트폴리오 3개 안(options)이야. "
    "각 안마다 사용자가 '이 추천은 믿을 만하다'고 느낄 수 있도록, 구체적인 근거를 들어 "
    "왜 이 조합을 추천하는지 설명하는 글(reason)을 만들어줘.\n\n"
    "티어의 의미:\n"
    "- 단순형: 주거래은행이나 이미 거래 중인 은행만으로, 새 계좌 없이 바로 가입할 수 있는 안.\n"
    "- 균형형: 새 은행 가입을 일부 감수하고 단순형보다 이자를 더 받는 안.\n"
    "- 최대형: 가입할 곳이 늘더라도 이자를 최대로 받는 안.\n\n"
    "입력 필드 설명:\n"
    "- products[].is_existing_bank: true=이미 거래 중인 은행, false=새로 가입해야 하는 은행, "
    "null=알 수 없음(이 경우 기존/신규 여부를 절대 언급하지 마).\n"
    "- products[].is_main_bank: true면 사용자의 주거래은행 상품.\n"
    "- products[].requires_membership: true면 신협·새마을금고 상품이라 조합원(회원) 가입"
    "(출자금 납입)이 필요해. 출자금 액수는 주어지지 않았으니 금액은 말하지 마.\n"
    "- products[].rate_gap_vs_simple: 단순형에서 가장 높은 금리보다 몇 %p 높은지(단순형 자신은 null, 0 이하면 금리 차이는 언급하지 마).\n"
    "- new_banks: 이 안을 실행하려면 새로 가입해야 하는 은행 이름 목록.\n"
    "- extra_vs_simple: 단순형보다 세후 이자를 몇 원 더 받는지(단순형 자신은 null).\n"
    "- same_term: true면 모든 상품의 만기(term_months)가 같아서 한 번에 찾을 수 있음.\n"
    "- best_extra_elsewhere: (단순형에만 있음) 새 가입을 감수하면 다른 안에서 최대 몇 원 더 "
    "받을 수 있는지, 그리고 그 안의 이름(best_extra_tier).\n\n"
    "글의 구성 (반드시 3문단으로 나누고 문단 사이에는 줄바꿈 두 번(\\n\\n)을 넣어. "
    "한 문단으로 이어 쓰지 마. 전체 4~6문장, 존댓말):\n"
    "1문단 - 무엇을 어떻게 담았는지: 각 상품을 왜 골랐는지(금리, rate_gap_vs_simple, "
    "기존 거래 은행인지) 와 금액을 어떻게 나눴는지(allocated_amount). 만기가 같으면 함께 "
    "찾을 수 있다는 점도.\n"
    "2문단 - 결과 숫자: 세후 이자 합계(after_tax_total). 단순형이 아니면 단순형보다 "
    "extra_vs_simple원 더 받는다는 점.\n"
    "3문단 - 실행할 때 알아둘 점: 단순형은 '추가 가입 없이 지금 계좌로 바로 가능'하다는 점과, "
    "best_extra_elsewhere가 있으면 '새 가입을 감수하면 {best_extra_tier}에서 최대 그만큼 더 받을 "
    "수 있다'는 안내. 균형형/최대형은 new_banks에 새로 가입해야 한다는 점과 "
    "requires_membership 상품의 조합원 가입 필요.\n\n"
    "반드시 지켜야 할 규칙:\n"
    "- 숫자는 절대 다시 계산하거나 바꾸지 마. 주어진 값을 그대로 인용만 해. 더하기·빼기·"
    "비율 계산도 하지 마. 차이는 extra_vs_simple, rate_gap_vs_simple, best_extra_elsewhere 값만 써.\n"
    "- 금액은 천 단위 콤마와 '원'을 붙여(예: 350,000원, 5,000,000원). 금리는 주어진 숫자에 %, "
    "금리 차이는 %p를 붙여.\n"
    "- 입력에 없는 정보(예금자보호, 중도해지 이율, 우대조건, 출자금 액수, 다른 상품, 시장 "
    "전망 등)는 언급하지 마.\n"
    "- is_existing_bank와 new_banks에 근거해서만 '기존 계좌로 가능', '새로 가입 필요'를 말해. "
    "단순형이라도 new_banks가 비어 있지 않으면 '추가 가입 없이'라고 쓰지 마.\n"
    "- 세 안이 비슷하게 읽히지 않게: 단순형은 편의성과 바로 실행 가능함, 균형형은 적은 "
    "추가 가입으로 얻는 이득, 최대형은 최대 수익과 그만큼의 가입 부담을 중심으로.\n"
    "- 과장 표현(무조건, 확실히, 최고의 등)은 쓰지 마.\n\n"
    "반드시 아래 JSON 형식으로만 응답해. 코드블록(```) 없이, 설명 문장 없이, "
    "순수 JSON 객체 하나만 출력해:\n"
    '{"reasons": [{"tier": "단순형", "reason": "1문단\\n\\n2문단\\n\\n3문단"}, '
    '{"tier": "균형형", "reason": "..."}, {"tier": "최대형", "reason": "..."}]}'
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


def _enrich_options(portfolio_options: list, user_context: Optional[dict]) -> list:
    """AI에 넘기기 전에, AI가 추측하면 안 되는 파생값을 코드로 미리 계산해서 붙인다.

    user_context 형태(없으면 None):
      {"main_bank_code": "BANK-0010927" | None,
       "held_bank_codes": ["BANK-0010927", "BANK-0015130", ...]}   # 보유(거래 중) 은행

    상품마다 붙이는 값:
      is_existing_bank    : 보유 은행 또는 주거래은행이면 True, 아니면 False,
                            institution_code나 user_context가 없으면 None(판정 불가)
      is_main_bank        : 주거래은행 상품이면 True
      requires_membership : 신협·새마을금고 상품이면 True - 조합원 가입(출자금 납입)이 필요해서
                            보유은행 목록과 상관없이 is_existing_bank=False로 고정
      rate_gap_vs_simple  : 단순형 상품 중 최고 금리 대비 몇 %p 높은지(단순형/비교불가면 None)
    안(option)마다 붙이는 값:
      new_banks            : 새로 가입해야 하는 은행 이름 목록(중복 제거)
      extra_vs_simple      : 단순형 대비 세후 이자 증가분(원). 단순형 자신/단순형 없음이면 None
      same_term            : 모든 상품 만기가 같으면 True
      best_extra_elsewhere : (단순형에만) 다른 안 중 extra_vs_simple 최댓값과 그 안 이름
                             -> "새 가입을 감수하면 최대 얼마 더"를 안내하는 데 씀
    FE의 vsSingleDiff(=extra_vs_simple), newAccountCount(=len(new_banks))와 같은 값이라
    BE가 응답 필드를 채울 때도 이 함수 결과를 그대로 쓸 수 있다.
    """
    main_code = (user_context or {}).get("main_bank_code")
    held = set((user_context or {}).get("held_bank_codes") or [])
    if main_code:
        held.add(main_code)
    can_judge = user_context is not None

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
        is_simple = opt.get("tier") == SIMPLE_TIER
        products = []
        new_banks: list = []
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

            rate = p.get("interest_rate")
            rate_gap = None
            if not is_simple and simple_best_rate is not None and isinstance(rate, (int, float)):
                rate_gap = round(rate - simple_best_rate, 2)

            products.append(
                {
                    **p,
                    "is_existing_bank": is_existing,
                    "is_main_bank": is_main,
                    "requires_membership": requires_membership,
                    "rate_gap_vs_simple": rate_gap,
                }
            )

        total = opt.get("after_tax_total")
        extra = None
        if not is_simple and isinstance(simple_total, int) and isinstance(total, int):
            extra = total - simple_total
        terms = {p.get("term_months") for p in products}

        enriched.append(
            {
                "tier": opt.get("tier"),
                "products": products,
                "after_tax_total": total,
                "new_banks": new_banks,
                "extra_vs_simple": extra,
                "same_term": len(products) > 1 and len(terms) == 1,
            }
        )

    # 단순형에 "다른 안을 고르면 최대 얼마 더"를 붙인다 (모든 안의 extra가 계산된 뒤라 별도 루프)
    others = [o for o in enriched if o["tier"] != SIMPLE_TIER and isinstance(o["extra_vs_simple"], int)]
    best = max(others, key=lambda o: o["extra_vs_simple"], default=None)
    for o in enriched:
        if o["tier"] == SIMPLE_TIER and best and best["extra_vs_simple"] > 0:
            o["best_extra_elsewhere"] = best["extra_vs_simple"]
            o["best_extra_tier"] = best["tier"]
    return enriched


def _fallback_reason(option: dict) -> str:
    """AI 호출이 끝까지 실패했을 때 쓰는 기본 문구. _enrich_options를 거친 option을
    받는다. 숫자를 지어내지 않고 계산된 값만으로, AI 버전과 같은 3문단 구성으로 만든다."""
    tier = option.get("tier", "")
    products = option.get("products", [])
    total = option.get("after_tax_total")
    total_str = f"{total:,}원" if isinstance(total, int) else "?"
    new_banks = option.get("new_banks") or []
    extra = option.get("extra_vs_simple")
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

    items = ", ".join(_item(p) for p in products[:3])
    para1 = f"{items}에 담은 조합입니다."
    if option.get("same_term"):
        para1 += " 모든 상품의 만기가 같아 한 번에 찾을 수 있습니다."

    para2 = f"세후 이자는 {total_str}입니다."
    if isinstance(extra, int) and extra > 0:
        para2 = f"세후 이자는 {total_str}으로, 단순형보다 {extra:,}원을 더 받습니다."

    notes = []
    if tier == SIMPLE_TIER:
        if all_existing:
            notes.append("추가 가입 없이 지금 거래 중인 계좌로 바로 시작할 수 있습니다.")
        if option.get("best_extra_elsewhere"):
            notes.append(
                f"새 은행 가입을 감수하면 {option['best_extra_tier']}에서 최대 "
                f"{option['best_extra_elsewhere']:,}원을 더 받을 수 있습니다."
            )
    else:
        if new_banks:
            notes.append(f"이를 위해 {', '.join(new_banks)}에 새로 가입해야 합니다.")
        if any(p.get("requires_membership") for p in products):
            notes.append("신협·새마을금고 상품은 조합원 가입(출자금 납입)이 필요합니다.")

    return "\n\n".join(x for x in [para1, para2, " ".join(notes)] if x)


def generate_summary(portfolio_options: list, user_context: Optional[dict] = None, retries: int = 3) -> dict:
    """포트폴리오 3개 티어를 받아서 {tier_이름: reason_문자열}을 반환한다.

    portfolio_options: PortfolioOptionOut과 같은 shape(reason은 없어도 됨).
    user_context: 위 _enrich_options 설명 참고. 없으면 기존/신규 은행 구분 없이 설명한다.

    AI 호출이 끝까지 실패하면 예외를 던지지 않고 _fallback_reason()으로 채운다 -
    Summary 실패가 전체 포트폴리오 응답을 막으면 안 되므로."""
    enriched = _enrich_options(portfolio_options, user_context)
    payload = json.dumps({"user": user_context, "options": enriched}, ensure_ascii=False)

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            client = _get_client()
            res = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": payload},
                ],
            )
            content = res.choices[0].message.content
            node = json.loads(_strip_code_fence(content))
            parsed = _find_valid_result(node)
            if parsed is None:
                raise ValueError(f"SummaryResult로 해석 안 됨. 원문 응답: {content[:300]}")
            reasons = {r.tier: r.reason for r in parsed.reasons}
            # AI가 티어를 하나 빼먹었으면 그 티어만 fallback으로 채운다
            for opt in enriched:
                reasons.setdefault(opt["tier"], _fallback_reason(opt))
            return reasons
        except Exception as e:  # noqa: BLE001
            last_error = e
            if attempt < retries:
                time.sleep(2**attempt)

    print(f"[Summary] AI 호출 실패 - fallback 사용: {last_error!r}", file=sys.stderr)
    return {opt["tier"]: _fallback_reason(opt) for opt in enriched}
