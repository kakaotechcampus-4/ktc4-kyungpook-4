import json
from collections import Counter
from pathlib import Path

FIXTURES = Path("tests/fixtures")
titles = Counter()

with (FIXTURES / "kfcc_rates.jsonl").open("r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        for category in ("거치식예탁금", "적립식예탁금"):
            for entry in rec.get(category, []):
                titles[entry["product_title"]] += 1

print(f"고유 상품명 수: {len(titles)}")
print(f"전체 (지점 x 상품) 조합 수: {sum(titles.values())}")
print("\n상품명별 지점 수 (많은 순):")
for title, cnt in titles.most_common():
    print(f"  {cnt:5d}건  {title}")
