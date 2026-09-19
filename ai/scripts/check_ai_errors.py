import json
from pathlib import Path
from collections import Counter

path = Path("output/ai_condition_cache.jsonl")
rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

failed = [r for r in rows if r.get("error")]
print(f"전체 {len(rows)}건 중 실패 {len(failed)}건\n")

print("=== 에러 메시지 종류별 건수 ===")
counts = Counter(r["error"][:200] for r in failed)
for msg, cnt in counts.most_common():
    print(f"{cnt}건: {msg}")

print("\n=== 실패 샘플 3건 (원문 앞부분 포함) ===")
for r in failed[:3]:
    print("-" * 60)
    print("파일:", r["filename"], "/ fin_prdt_cd:", r["fin_prdt_cd"])
    print("spcl_cnd 앞부분:", r["spcl_cnd"][:150])
    print("에러:", r["error"])