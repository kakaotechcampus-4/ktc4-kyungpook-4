"""
[v2] 지금 남아있는 MISMATCH들을 만기(term)별로 실제 공시 우대폭 vs AI 추출 합계를
나란히 까서 보여주는 진단 스크립트. (이전 check_mismatch_samples.py는 캐시를 키 기준으로
중복 제거 안 하고 그냥 다 읽어서 집계가 부정확할 수 있었음 - 이번엔 extract_conditions_ai.py의
load_cache()와 똑같은 방식으로 "성공한 것 중 마지막 값"만 남기고, error 있는 행은 버림)

만기별로 어떤 조건이 적용됐다고 판단했는지(group_id, overall_max_bonus_rate 포함)까지
같이 보여줘서, "이건 스키마/프롬프트를 더 고치면 되는 문제"인지 "원문 자체가 애매해서
사람이 봐도 갈리는 문제"인지 구분하는 데 씀.

--limit N을 주면 extract_conditions_ai.py --limit N으로 방금 처리한 범위만 골라서 보여줌
(안 주면 캐시 전체 대상).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from scripts.extract_conditions_ai import (
    condition_applies, compute_extracted_total, parse_term_months, gather_targets,
)

CACHE_PATH = Path(__file__).resolve().parent.parent / "output" / "ai_condition_cache.jsonl"


def load_cache_dedup():
    # extract_conditions_ai.py의 load_cache()와 동일한 규칙:
    # error 있는 행은 캐시로 안 치고, 같은 key는 마지막(=가장 최근 실행) 값으로 덮어씀.
    cache = {}
    with CACHE_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("error"):
                cache.pop(row["key"], None)
                continue
            cache[row["key"]] = row
    return cache


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="gather_targets() 앞에서부터 이 건수만 대상으로 함(extract_conditions_ai.py를 "
                         "--limit N으로 돌렸을 때랑 똑같은 N을 주면, 그때 처리한 상품만 골라서 보여줌)")
    args = ap.parse_args()

    cache = load_cache_dedup()
    all_targets = gather_targets()
    if args.limit:
        all_targets = all_targets[: args.limit]
    target_keys = {t["key"] for t in all_targets}
    # 캐시 행에는 opts(만기별 실제 공시금리)가 저장되어 있지 않으므로(용량 절약 목적으로
    # 원래부터 안 남김), 원본 소스 파일에서 다시 만들어서 key로 매칭한다.
    opts_by_key = {t["key"]: t["opts"] for t in all_targets}

    # --limit을 준 경우 그 범위 안의 key만, 안 준 경우 캐시 전체를 대상으로 함.
    scoped_cache = {k: v for k, v in cache.items() if (not args.limit) or (k in target_keys)}
    mismatches = [row for row in scoped_cache.values() if row["verification_status"] == "MISMATCH"]

    print(f"=== 대상 {len(scoped_cache)}건 (중복 제거 후{', --limit ' + str(args.limit) + ' 범위' if args.limit else ''}) ===")
    from collections import Counter
    print("검증 상태 분포:", dict(Counter(r["verification_status"] for r in scoped_cache.values())))
    print(f"MISMATCH: {len(mismatches)}건\n")
    print("=" * 80)

    for row in mismatches:
        overall_cap = row.get("overall_max_bonus_rate")
        print(f"\n[{row['key']}]")
        print(f"원문: {row['spcl_cnd'][:300]}")
        if overall_cap is not None:
            print(f"AI가 인식한 전체 상한(overall_max_bonus_rate): {overall_cap}%p")
        print("AI 추출 조건:")
        for c in row["conditions"]:
            term_desc = []
            if c.get("applicable_term_months") is not None:
                term_desc.append(f"정확히{c['applicable_term_months']}개월")
            if c.get("min_term_months") is not None:
                term_desc.append(f">={c['min_term_months']}개월")
            if c.get("max_term_months") is not None:
                term_desc.append(f"<={c['max_term_months']}개월")
            term_str = ",".join(term_desc) if term_desc else "전체만기"
            grp = f" [그룹:{c['group_id']}]" if c.get("group_id") else ""
            print(f"  - {c['description']} : {c['bonus_rate']}%p ({term_str}){grp}")

        print("만기별 비교 (공시우대폭 vs AI추출합계):")
        for opt in opts_by_key.get(row["key"], []) or []:
            base_rate = opt.get("intr_rate")
            max_rate = opt.get("intr_rate2")
            if base_rate is None or max_rate is None:
                continue
            disclosed = round(max_rate - base_rate, 4)
            term_months = parse_term_months(opt.get("save_trm"))
            extracted = compute_extracted_total(row["conditions"], term_months, overall_cap)
            diff = round(disclosed - extracted, 4)
            mark = "  <- 불일치" if abs(diff) > 0.05 else ""
            applied = [c["description"] for c in row["conditions"] if condition_applies(c, term_months)]
            print(f"  {term_months}개월: 공시={disclosed}%p / AI합계={extracted}%p / 차이={diff}{mark}")
            if mark:
                print(f"      (이 만기에 적용된 조건: {applied})")
        print("-" * 80)


if __name__ == "__main__":
    main()