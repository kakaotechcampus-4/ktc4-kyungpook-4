"""
kfcc_rates.jsonl 안에 "-" 나 빈 문자열, 그 외 숫자가 아닌 금리 값이
있는지 확인 -> 있으면 사이트가 "취급안함"을 다른 기호로도 표시한다는 뜻이고,
"연0.0%"만 있고 "-"가 하나도 없다면 0.0%가 실제 화면 표시 그대로일 가능성이 높음.
"""
import json
import re
from collections import Counter
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
PCT_RE = re.compile(r"(\d+(?:\.\d+)?)")

value_patterns = Counter()
non_numeric_samples = []

path = FIXTURES / "kfcc_rates.jsonl"
with path.open("r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        for category in ("거치식예탁금", "적립식예탁금"):
            for entry in rec.get(category, []):
                headers = entry.get("headers", [])
                rows = entry.get("rows", [])
                for row in rows:
                    for cell in row:
                        if cell is None:
                            continue
                        cell_s = str(cell).strip()
                        if PCT_RE.search(cell_s) and ("%" in cell_s or "연" in cell_s):
                            # 숫자%처럼 생긴 값 -> 실제 값이 뭔지 정규화해서 카운트
                            if cell_s.startswith("연0.0%") or cell_s == "0.0%" or cell_s == "0%":
                                value_patterns["0.0%류"] += 1
                            else:
                                value_patterns["숫자%(0 아님)"] += 1
                        elif cell_s in ("-", "－", "‐", "", "취급안함", "해당없음", "미취급", "N/A"):
                            value_patterns[f"비숫자 기호: '{cell_s}'"] += 1
                            if len(non_numeric_samples) < 5:
                                non_numeric_samples.append(row)
                        # 그 외(상품명, 기간 텍스트 등)는 카운트 안 함

print("=== rows 안의 '금리처럼 보이는 값' 패턴 분포 ===")
for k, v in value_patterns.most_common():
    print(f"  {k}: {v}건")

print()
if non_numeric_samples:
    print("=== '-' 등 비숫자 기호가 나온 row 샘플 ===")
    for r in non_numeric_samples:
        print(" ", r)
else:
    print("=== '-' 같은 비숫자 기호는 한 건도 없음 ===")