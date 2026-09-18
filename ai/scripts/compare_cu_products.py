import json, re
from pathlib import Path

FIXTURES = Path("tests/fixtures")

def normalize(name):
    if not name:
        return ""
    name = name.strip()
    name = re.sub(r"(신용협동조합|신협)$", "", name).strip()
    name = re.sub(r"\s+", "", name)
    return name

finlife_counts = {}
for fname, ptype in (("deposit_cu_sample.json", "deposit"), ("saving_cu_sample.json", "saving")):
    path = FIXTURES / fname
    if not path.exists():
        print(f"[!] {fname} 없음")
        continue
    data = json.loads(path.read_text(encoding="utf-8"))
    result = data.get("result", data)
    for b in result.get("baseList", []):
        key = normalize(b.get("kor_co_nm"))
        finlife_counts.setdefault(key, {"deposit": 0, "saving": 0})
        finlife_counts[key][ptype] += 1

cu_counts = {}
with (FIXTURES / "cu_rate_compare.jsonl").open("r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        key = normalize(rec.get("cuNm"))
        ptype = rec.get("_product_type") or "unknown"
        cu_counts.setdefault(key, {"deposit": 0, "saving": 0})
        cu_counts[key][ptype] = cu_counts[key].get(ptype, 0) + 1

gap_deposit, gap_saving = [], []
for inst, counts in finlife_counts.items():
    cu_c = cu_counts.get(inst, {"deposit": 0, "saving": 0})
    if counts["deposit"] > 0 and cu_c.get("deposit", 0) == 0:
        gap_deposit.append((inst, counts["deposit"]))
    if counts["saving"] > 0 and cu_c.get("saving", 0) == 0:
        gap_saving.append((inst, counts["saving"]))

print(f"finlife 기관 수: {len(finlife_counts)}, cu.co.kr 기관 수: {len(cu_counts)}")
print(f"\n[예금] finlife엔 있는데 cu.co.kr엔 예금상품 0건인 기관: {len(gap_deposit)}개")
for inst, n in gap_deposit[:30]:
    print(f"  - {inst}: finlife {n}건")
print(f"\n[적금] finlife엔 있는데 cu.co.kr엔 적금상품 0건인 기관: {len(gap_saving)}개")
for inst, n in gap_saving[:30]:
    print(f"  - {inst}: finlife {n}건")
