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

finlife_institutions = {}
finlife_products = 0
for fname in ("deposit_cu_sample.json", "saving_cu_sample.json"):
    path = FIXTURES / fname
    if not path.exists():
        print(f"[!] {fname} 없음 - 스킵 (이미 지웠으면 이 비교 못함)")
        continue
    data = json.loads(path.read_text(encoding="utf-8"))
    result = data.get("result", data)
    for b in result.get("baseList", []):
        raw = b.get("kor_co_nm")
        finlife_institutions.setdefault(normalize(raw), set()).add(raw)
        finlife_products += 1

cu_institutions = {}
cu_records = 0
with (FIXTURES / "cu_rate_compare.jsonl").open("r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        raw = rec.get("cuNm")
        cu_institutions.setdefault(normalize(raw), set()).add(raw)
        cu_records += 1

fset, cset = set(finlife_institutions), set(cu_institutions)
both = fset & cset
only_f = fset - cset
only_c = cset - fset

print(f"finlife 신협 기관 수(정규화 후): {len(fset)}, 상품(baseList) 레코드 수: {finlife_products}")
print(f"cu.co.kr 기관 수(정규화 후): {len(cset)}, 원본 레코드 수: {cu_records}")
print(f"\n양쪽 다 있는 기관: {len(both)}")
print(f"finlife에만 있는 기관 (cu.co.kr 쪽에 없을 수 있는 후보, 최대 30개):")
for name in sorted(only_f)[:30]:
    print("  -", finlife_institutions[name])
print(f"\ncu.co.kr에만 있는 기관 (최대 10개):")
for name in sorted(only_c)[:10]:
    print("  -", cu_institutions[name])
