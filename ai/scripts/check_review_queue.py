import json
from pathlib import Path

for name in ["review_queue.json", "review_queue_cu_saving.json"]:
    p = Path("logs") / name
    print(f"===== {name} =====")
    if not p.exists():
        print("  파일 없음")
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, list):
        print(f"  리스트, 총 {len(data)}건")
        for item in data[:2]:
            print("  샘플:", json.dumps(item, ensure_ascii=False)[:500])
    elif isinstance(data, dict):
        print(f"  딕셔너리, 키: {list(data.keys())}")
        print("  내용 일부:", json.dumps(data, ensure_ascii=False)[:800])
    print()