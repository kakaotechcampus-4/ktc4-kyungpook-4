"""
Summary(호출 B) 로컬 품질 확인 스크립트.

본체 로직은 src/summary.py로 옮겼다(BE가 패키지 `ktc4_ai.summary`로 가져다 쓰도록).
이 파일은 손으로 만든 예시 포트폴리오로 AI 응답을 눈으로 확인하는 용도만 남긴다.

    cd ai
    python scripts/summary_prompt.py
"""
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.summary import ALWAYS_NEW_CODE_PREFIXES, TIERS, _enrich_options, generate_summary  # noqa: E402


if __name__ == "__main__":
    # 계산 엔진이 아직 새 티어 정의(2026-10-13)를 반영 안 해서, 손으로 만든 예시로 자체 점검.
    # 시나리오: 주거래 국민은행, 카카오뱅크도 보유. 목돈 1,000만원 / 12개월.
    sample_user = {
        "main_bank_code": "BANK-0010927",  # 국민은행
        # 국민은행, 카카오뱅크, 그리고 신협(CU-02022)도 보유로 골랐다고 가정 -
        # 신협은 그래도 신규 가입으로 잡혀야 함(ALWAYS_NEW_CODE_PREFIXES)
        "held_bank_codes": ["BANK-0010927", "BANK-0015130", "CU-02022"],
    }

    # 단일형: 주거래 은행(국민은행) 1위 상품 하나에 전액. reason은 만들지 않음.
    sample_baseline = {
        "institution_name": "국민은행",
        "product_name": "KB Star 정기예금",
        "after_tax_total": 245_340,
        "exceeds_protection": False,
    }

    def _p(code, inst, name, rate, amount, interest, conditions=None):
        return {
            "institution_code": code,
            "institution_name": inst,
            "product_name": name,
            "term_months": 12,
            "interest_rate": rate,
            "allocated_amount": amount,
            "after_tax_interest": interest,
            "applied_conditions": conditions or [],
        }

    def _c(ctype, met, value=None, unit=None):
        return {"condition_type": ctype, "bonus_rate": 0.2, "threshold_value": value,
                "threshold_unit": unit, "already_met": met}

    sample_portfolio = [
        {
            "tier": "단순형",
            "products": [_p("BANK-0015130", "카카오뱅크", "정기예금", 3.1, 10_000_000, 262_260)],
            "after_tax_total": 262_260,
        },
        {
            "tier": "균형형",
            "products": [
                _p("BANK-0015130", "카카오뱅크", "정기예금", 3.1, 7_000_000, 183_580),
                _p("CU-02022", "HJ중공업신협", "정기예탁금", 3.9, 3_000_000, 115_380,
                   [_c("자동이체", False, 10, "만원"), _c("비대면가입", False)]),
            ],
            "after_tax_total": 298_960,
            "tax_saving_won": 16_380,
        },
        {
            "tier": "최대형",
            "products": [
                _p("SB-0010370", "SBI저축은행", "정기예금", 3.8, 7_000_000, 225_040,
                   [_c("카드실적", False, 30, "만원"), _c("마케팅동의", False)]),
                _p("CU-02022", "HJ중공업신협", "정기예탁금", 4.3, 3_000_000, 127_220,
                   [_c("공제가입", False), _c("급여이체", False, 50, "만원")]),
            ],
            "after_tax_total": 352_260,
            "tax_saving_won": 18_060,
        },
        {
            "tier": "안정형",
            "products": [
                _p("BANK-0015130", "카카오뱅크", "정기예금", 3.1, 5_000_000, 131_130),
                _p("BANK-0010927", "국민은행", "KB Star 정기예금", 3.0, 5_000_000, 126_900,
                   [_c("자동이체", True)]),
            ],
            "after_tax_total": 258_030,
        },
    ]

    enriched = _enrich_options(sample_portfolio, sample_user, sample_baseline)
    print("=== AI에 넘어가는 입력(payload) ===")
    print(json.dumps({"baseline": sample_baseline, "options": enriched}, ensure_ascii=False, indent=2))
    print()

    reasons = generate_summary(sample_portfolio, sample_user, sample_baseline)
    print("=== Summary 결과 ===")
    for tier, reason in reasons.items():
        print(f"[{tier}]\n{reason}\n")

    # --- 구조 점검 ---
    by_tier = {o["tier"]: o for o in enriched}
    assert set(reasons.keys()) == set(TIERS), reasons.keys()
    # 신협은 보유로 골랐어도 신규 가입 + 조합원 가입 필요
    _cu = [p for o in enriched for p in o["products"]
           if p["institution_code"].startswith(ALWAYS_NEW_CODE_PREFIXES)]
    assert all(p["is_existing_bank"] is False and p["requires_membership"] for p in _cu), _cu
    # 안정형은 단순형과 비교하지 않음
    assert by_tier["안정형"]["extra_vs_simple"] is None
    assert all(p["rate_gap_vs_simple"] is None for p in by_tier["안정형"]["products"])
    # 단일형 대비 차이는 모든 안에 계산됨
    assert by_tier["단순형"]["extra_vs_baseline"] == 262_260 - 245_340
    # 최대형은 보험(공제) 조건 표시, 이미 충족한 조건은 할 일에서 빠짐
    assert by_tier["최대형"]["has_insurance_condition"] is True
    assert by_tier["안정형"]["required_actions"] == []
    # 단순형의 '최대 얼마 더'는 균형형·최대형 중에서만
    assert by_tier["단순형"]["best_extra_tier"] == "최대형"
    # AI 입력에서 applied_conditions 원본은 빠짐
    assert all("applied_conditions" not in p for o in enriched for p in o["products"])
    print()
    print("OK (AI 호출 실패 시 fallback 문구로 대체됐어도 구조는 정상)")