"""
base_rate == 0%로 나온 케이스의 원인을 진단.
period_months(원본 monTy) / reserve_type / 기관별로 분포를 보고,
원본 레코드 몇 건을 그대로 출력해서 실제 원인을 확인한다.
"""
import json
import re
from collections import Counter
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

PCT_RE = re.compile(r"(\d+(?:\.\d+)?)")


def parse_pct(s):
    if s is None:
        return None
    m = PCT_RE.search(str(s))
    return float(m.group(1)) if m else None


def is_freeform(name: str) -> bool:
    return "자유" in name


zero_by_monty = Counter()
zero_by_product_type = Counter()
zero_by_cu = Counter()
total_by_monty = Counter()
raw_samples = []

with (FIXTURES / "cu_rate_compare.jsonl").open("r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        base_rate = parse_pct(rec.get("baseRate"))
        mon_ty = rec.get("monTy")
        total_by_monty[mon_ty] += 1

        if base_rate == 0.0:
            zero_by_monty[mon_ty] += 1
            ptype = rec.get("_product_type")
            name = rec.get("stockNm", "")
            zero_by_product_type[(ptype, "자유적립식" if is_freeform(name) else "정액적립식/거치식")] += 1
            zero_by_cu[rec.get("cuIngno")] += 1
            if len(raw_samples) < 10:
                raw_samples.append(rec)

print("=== 전체 레코드 monTy(원본 기간코드)별 분포 ===")
for k, v in sorted(total_by_monty.items(), key=lambda x: str(x[0])):
    print(f"  monTy={k}: {v}건")

print()
print("=== base_rate==0 인 레코드의 monTy별 분포 ===")
for k, v in sorted(zero_by_monty.items(), key=lambda x: str(x[0])):
    print(f"  monTy={k}: {v}건 (전체 {total_by_monty[k]}건 중)")

print()
print("=== base_rate==0 인 레코드의 상품유형별 분포 ===")
for k, v in zero_by_product_type.most_common():
    print(f"  {k}: {v}건")

print()
print(f"=== base_rate==0 이 발생한 서로 다른 신협(cuIngno) 개수: {len(zero_by_cu)}개 ===")
print("상위 5개:", zero_by_cu.most_common(5))

print()
print("=== 원본 레코드 샘플 10건 (그대로) ===")
for r in raw_samples:
    print(" ", json.dumps(r, ensure_ascii=False))