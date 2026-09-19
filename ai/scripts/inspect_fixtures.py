import json
from pathlib import Path

FIXTURES = Path("tests/fixtures")

for f in sorted(FIXTURES.glob("*")):
    if not f.is_file():
        continue
    size_kb = f.stat().st_size / 1024
    print(f"\n=== {f.name} ({size_kb:.1f} KB) ===")
    try:
        if f.suffix == ".jsonl":
            lines = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
            print(f"  레코드 수: {len(lines)}")
            if lines:
                first = json.loads(lines[0])
                print(f"  첫 레코드 키: {list(first.keys())}")
                for k in ("finPrdtNm", "gmgoNm", "cuNm", "kfccNm", "divNm", "finPrdtCd", "prdtNm", "topFinGrpNo"):
                    if k in first:
                        print(f"    {k}: {first[k]}")
        elif f.suffix == ".json":
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                print(f"  리스트 길이: {len(data)}")
                if data and isinstance(data[0], dict):
                    print(f"  첫 항목 키: {list(data[0].keys())}")
            elif isinstance(data, dict):
                print(f"  최상위 키: {list(data.keys())}")
    except Exception as e:
        print(f"  [읽기 실패: {e}]")
