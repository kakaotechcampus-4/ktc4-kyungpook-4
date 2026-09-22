import json
from pathlib import Path

rows = [json.loads(l) for l in Path("output/ai_condition_cache.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
mismatches = [r for r in rows if r["verification_status"] == "MISMATCH"]
matches = [r for r in rows if r["verification_status"] == "MATCHED"]

print(f"MATCHED {len(matches)}건 / MISMATCH {len(mismatches)}건\n")

print("=== MISMATCH 샘플 (원문 + AI가 뽑은 조건들) ===")
for r in mismatches[:5]:
    print("-" * 70)
    print("상품:", r["fin_prdt_cd"], "/", r["filename"])
    print("원문:")
    print(" ", r["spcl_cnd"].replace("\n", "\n  "))
    print("AI가 뽑은 조건:")
    for c in r["conditions"]:
        print(f"   - {c['description']}: {c['bonus_rate']}%p (적용만기={c.get('applicable_term_months')}, 최소만기={c.get('min_term_months')})")
    print()