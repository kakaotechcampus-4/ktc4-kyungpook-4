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
from src.summary import ALWAYS_NEW_CODE_PREFIXES, _enrich_options, generate_summary  # noqa: E402


if __name__ == "__main__":
    # 계산 엔진이 아직 새 티어 정의를 반영 안 해서, 손으로 만든 예시로 자체 점검.
    # 시나리오: 주거래 국민은행, 카카오뱅크도 보유. 목돈 1,000만원 / 12개월.
    sample_user = {
        "main_bank_code": "BANK-0010927",  # 국민은행
        # 국민은행, 카카오뱅크, 그리고 신협(CU-02022)도 보유로 골랐다고 가정 -
        # 신협은 그래도 신규 가입으로 잡혀야 함(ALWAYS_NEW_CODE_PREFIXES)
        "held_bank_codes": ["BANK-0010927", "BANK-0015130", "CU-02022"],
    }

    def _p(code, inst, name, rate, amount, interest):
        return {
            "institution_code": code,
            "institution_name": inst,
            "product_name": name,
            "term_months": 12,
            "interest_rate": rate,
            "allocated_amount": amount,
            "after_tax_interest": interest,
        }

    sample_portfolio = [
        {
            "tier": "단순형",
            "products": [_p("BANK-0015130", "카카오뱅크", "정기예금", 3.1, 10_000_000, 262_260)],
            "after_tax_total": 262_260,
        },
        {
            "tier": "균형형",
            "products": [
                _p("BANK-0015130", "카카오뱅크", "정기예금", 3.1, 5_000_000, 131_130),
                _p("SB-0010370", "SBI저축은행", "정기예금", 3.6, 5_000_000, 152_280),
            ],
            "after_tax_total": 283_410,
        },
        {
            "tier": "최대형",
            "products": [
                _p("SB-0010370", "SBI저축은행", "정기예금", 3.6, 5_000_000, 152_280),
                _p("CU-02022", "HJ중공업신협", "정기예탁금", 3.9, 5_000_000, 164_970),
            ],
            "after_tax_total": 317_250,
        },
    ]

    print("=== AI에 넘어가는 입력(payload) ===")
    print(json.dumps(_enrich_options(sample_portfolio, sample_user), ensure_ascii=False, indent=2))
    print()

    reasons = generate_summary(sample_portfolio, sample_user)
    print("=== Summary 결과 ===")
    for tier, reason in reasons.items():
        print(f"[{tier}]\n{reason}\n")

    assert set(reasons.keys()) == {"단순형", "균형형", "최대형"}, reasons.keys()
    _cu = [p for o in _enrich_options(sample_portfolio, sample_user) for p in o["products"]
           if p["institution_code"].startswith(ALWAYS_NEW_CODE_PREFIXES)]
    assert all(p["is_existing_bank"] is False and p["requires_membership"] for p in _cu), _cu
    print()
    print("OK (AI 호출 실패 시 fallback 문구로 대체됐어도 구조는 정상)")
