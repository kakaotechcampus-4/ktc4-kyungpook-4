#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
티어별 세후 실수령액 비교 테스트

[원칙]
  - DB: 상품 데이터 SELECT 전용 (INSERT / UPDATE / DELETE 없음)
  - 백엔드 파일: 수정 없음 — import 해서 읽기만 한다

[동작 방식]
  1. test_cases.json 에서 더미 유저 입력 300건 로드
  2. build_tiers(session, profile) 로 DB에서 상품 SELECT → 티어별 배분 계산
     - profile_id=-1 → get_held_bank_codes SELECT → 빈 결과 (보유 기관 없음)
     - main_bank_code 1곳만 기존 거래, 나머지 모두 신규 판정
  3. _calc() / TaxContext 로 세후 실수령액 계산
  4. 결과를 콘솔 및 results.jsonl 로 출력

[실행]
  cd backend
  uv run python ../ai/scripts/compare_tiers.py            # 전체 300건
  uv run python ../ai/scripts/compare_tiers.py --limit 10 # 처음 N건만
  uv run python ../ai/scripts/compare_tiers.py --group A   # 특정 그룹만

[현재 DB 상태]
  신협·새마을금고 상품만 적재됨 (은행 JSONL 미생성)
  → 안정형(1금융권 전용)은 해당 상품 없어 빈 결과로 나온다
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# backend 패키지를 import 경로에 추가 (파일 수정 없음)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from app.db.session import SessionLocal
from app.services.portfolio import (
    BALANCED_TIER,
    MAX_TIER,
    SIMPLE_TIER,
    STABLE_TIER,
    _calc,
    _tax_context,
    build_tiers,
)

TEST_CASES_PATH = Path(__file__).parent / "test_cases.json"
RESULTS_PATH    = Path(__file__).parent / "tier_results.jsonl"
RESULTS_PATH_V2 = Path(__file__).parent / "tier_results_340.jsonl"

TIER_ORDER = ["단일형", SIMPLE_TIER, BALANCED_TIER, MAX_TIER, STABLE_TIER]


# ---------------------------------------------------------------------------
# 더미 유저 입력 → MockProfile
# ---------------------------------------------------------------------------

@dataclass
class MockProfile:
    """
    build_tiers / _calc 가 참조하는 필드만 정의한 더미 프로필.

    profile_id = -1
        존재하지 않는 ID → get_held_bank_codes() SELECT 가 빈 리스트 반환
        → held = {} → codes = {main_bank_code}
        → main_bank 외 모든 기관이 '신규 기관'으로 판정
        ≒ "주거래은행 한 곳만 갖고 있는 일반 사용자"
    """

    profile_id: int = -1
    capital: int = 0
    monthly_saving: int = 0
    period_months: int = 12
    main_bank_code: str | None = None
    marketing_consent: bool | None = True
    app_install: bool | None = True
    auto_transfer: bool | None = True
    accepts_membership: bool | None = True
    coop_tax_eligible: bool | None = True
    coop_exempt_used: int | None = 0


def load_profile(tc: dict) -> MockProfile:
    return MockProfile(
        capital=tc["capital"],
        monthly_saving=tc["monthly_saving"],
        period_months=tc["period_months"],
        main_bank_code=tc["main_bank_code"],
        marketing_consent=tc["marketing_consent"],
        app_install=tc["app_install"],
        auto_transfer=tc["auto_transfer"],
        accepts_membership=tc["accepts_membership"],
        coop_tax_eligible=tc["coop_tax_eligible"],
        coop_exempt_used=tc["coop_exempt_used"],
    )


# ---------------------------------------------------------------------------
# 계산
# ---------------------------------------------------------------------------

async def run_test_case(session, tc: dict) -> dict:
    profile = load_profile(tc)

    # DB SELECT: 상품·옵션·조건 조회 + 티어별 배분 계산 (백엔드 파일 수정 없음)
    plan = await build_tiers(session, profile)
    today = date.today()

    tiers: dict[str, dict | None] = {}

    if plan.baseline:
        nums = _calc(plan.baseline, _tax_context(profile, today))
        tiers["단일형"] = {
            "after_tax": nums.after_tax_total,
            "n_deposit": len(plan.baseline.deposit_allocs),
            "n_installment": len(plan.baseline.installment_allocs),
            "products": [
                {
                    "institution": p.institution_name,
                    "product": p.product_name,
                    "base_rate": p.base_rate,
                    "effective_rate": p.interest_rate,
                    "allocated": p.allocated_amount,
                    "after_tax_interest": p.after_tax_interest,
                    "new_conditions": [c.condition_type for c in p.applied_conditions if not c.already_met],
                }
                for p in nums.products
            ],
        }
    else:
        tiers["단일형"] = None

    for tier_name, allocs in plan.tiers.items():
        nums = _calc(allocs, _tax_context(profile, today))
        tiers[tier_name] = {
            "after_tax": nums.after_tax_total,
            "n_deposit": len(allocs.deposit_allocs),
            "n_installment": len(allocs.installment_allocs),
            "products": [
                {
                    "institution": p.institution_name,
                    "product": p.product_name,
                    "base_rate": p.base_rate,
                    "effective_rate": p.interest_rate,
                    "allocated": p.allocated_amount,
                    "after_tax_interest": p.after_tax_interest,
                    "new_conditions": [c.condition_type for c in p.applied_conditions if not c.already_met],
                }
                for p in nums.products
            ],
        }

    return {"id": tc["id"], "label": tc["label"], "input": tc, "tiers": tiers}


# ---------------------------------------------------------------------------
# 출력
# ---------------------------------------------------------------------------

def print_result(result: dict) -> None:
    tc     = result["input"]
    tiers  = result["tiers"]
    cap_str = f"{tc['capital']:,}원" if tc["capital"] else "없음"
    sav_str = f"{tc['monthly_saving']:,}원/월" if tc["monthly_saving"] else "없음"

    print(f"\n[{result['id']:03d}] {result['label']}")
    print(f"  목돈:{cap_str}  월저축:{sav_str}  기간:{tc['period_months']}개월"
          f"  주거래:{tc['main_bank_code']}")

    baseline_at = tiers["단일형"]["after_tax"] if tiers.get("단일형") else None

    print(f"  {'티어':<8} {'세후이자':>14} {'단일형대비':>13} {'예금':>4} {'적금':>4}")
    print(f"  {'-'*50}")

    for tier in TIER_ORDER:
        r = tiers.get(tier)
        if r is None or r["after_tax"] == 0:
            print(f"  {tier:<8} {'(해당없음)':>14} {'—':>13} {'—':>4} {'—':>4}")
            continue
        at = r["after_tax"]
        if baseline_at is not None and tier != "단일형":
            diff = at - baseline_at
            sign = "+" if diff >= 0 else ""
            diff_str = f"{sign}{diff:,}원"
        else:
            diff_str = "—"
        print(f"  {tier:<8} {at:>13,}원 {diff_str:>13} {r['n_deposit']:>4} {r['n_installment']:>4}")

    # 상품 상세 (단일형과 내용이 다른 티어만)
    for tier in TIER_ORDER:
        r = tiers.get(tier)
        if not r or not r["products"]:
            continue
        print(f"  [{tier}]", end="")
        for p in r["products"]:
            cond = f" (신규조건: {','.join(p['new_conditions'])})" if p["new_conditions"] else ""
            print(f"\n    {p['institution']} | {p['product']}"
                  f"\n      기본{p['base_rate']:.2f}%→실효{p['effective_rate']:.2f}%"
                  f"  배분{p['allocated']:,}원  세후이자{p['after_tax_interest']:,}원{cond}")
        print()


def print_summary(results: list[dict]) -> None:
    print("\n" + "=" * 72)
    print("  요약")
    print("=" * 72)

    total = len(results)
    gains: dict[str, list[int]] = {t: [] for t in [SIMPLE_TIER, BALANCED_TIER, MAX_TIER, STABLE_TIER]}

    for r in results:
        tiers = r["tiers"]
        baseline_at = tiers["단일형"]["after_tax"] if tiers.get("단일형") else None
        if baseline_at is None:
            continue
        for tier in [SIMPLE_TIER, BALANCED_TIER, MAX_TIER, STABLE_TIER]:
            t = tiers.get(tier)
            if t and t["after_tax"] > 0:
                gains[tier].append(t["after_tax"] - baseline_at)

    print(f"  총 테스트 케이스: {total}건")
    for tier in [SIMPLE_TIER, BALANCED_TIER, MAX_TIER, STABLE_TIER]:
        g = gains[tier]
        if not g:
            print(f"  {tier}: 데이터 없음")
            continue
        avg = sum(g) // len(g)
        mx  = max(g)
        mn  = min(g)
        pos = sum(1 for x in g if x > 0)
        neg = sum(1 for x in g if x < 0)
        print(f"  {tier} (단일형 대비):")
        print(f"    평균 차액: {avg:+,}원  최대: {mx:+,}원  최소: {mn:+,}원")
        print(f"    유리한 케이스: {pos}/{len(g)}건  불리한 케이스: {neg}/{len(g)}건")


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

async def main(args: argparse.Namespace) -> None:
    test_cases: list[dict] = json.loads(TEST_CASES_PATH.read_text(encoding="utf-8"))

    # 필터링
    if args.group:
        test_cases = [tc for tc in test_cases if tc["label"].startswith(args.group.upper())]
    if args.limit:
        test_cases = test_cases[: args.limit]

    print("=" * 72)
    print("  티어별 세후 실수령액 비교 테스트")
    print("=" * 72)
    total_cases = len(json.loads(TEST_CASES_PATH.read_text(encoding="utf-8")))
    print(f"  테스트 케이스: {len(test_cases)}건  (전체 {total_cases}건 중)")
    print("  ※ DB 접근: 상품 데이터 SELECT 전용 (수정 없음)")
    print("  ※ 백엔드 파일: 수정 없음 (import 전용)")
    print("  ※ 현재 DB: 신협·새마을금고 + 은행·저축은행 상품 적재")

    results = []
    async with SessionLocal() as session:
        for i, tc in enumerate(test_cases, 1):
            try:
                result = await run_test_case(session, tc)
                results.append(result)
                if not args.quiet:
                    print_result(result)
            except Exception as e:
                print(f"  [오류] id={tc['id']} {tc['label']}: {e}")

    print_summary(results)

    # JSONL 저장
    save_path = RESULTS_PATH_V2 if not args.group and not args.limit else RESULTS_PATH
    with save_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n  결과 저장: {save_path} ({len(results)}건)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="티어별 실수령액 비교 테스트")
    parser.add_argument("--limit", type=int, default=None, help="실행할 케이스 수 (기본: 전체)")
    parser.add_argument("--group", type=str, default=None, help="그룹 필터 (A~J)")
    parser.add_argument("--quiet", action="store_true", help="요약만 출력 (상세 생략)")
    args = parser.parse_args()
    asyncio.run(main(args))
