import json
from pathlib import Path

FIXTURES = Path("tests/fixtures")
KEYWORDS = ["우대", "조건", "가산", "이벤트", "특판", "실적", "%"]

def walk(obj, hits):
    if isinstance(obj, str):
        for kw in KEYWORDS:
            if kw in obj:
                hits.append((kw, obj[:80]))
                return
    elif isinstance(obj, dict):
        for v in obj.values():
            walk(v, hits)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, hits)

def scan_jsonl(path, nested_keys_of_interest=()):
    all_keys = set()
    nested_keys = set()
    hits = []
    n = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n += 1
            rec = json.loads(line)
            all_keys |= set(rec.keys())
            for nk in nested_keys_of_interest:
                for entry in rec.get(nk, []):
                    if isinstance(entry, dict):
                        nested_keys |= set(entry.keys())
            walk(rec, hits)
    return n, all_keys, nested_keys, hits

print("=== kfcc_rates.jsonl ===")
n, keys, nested, hits = scan_jsonl(FIXTURES / "kfcc_rates.jsonl", ("거치식예탁금", "적립식예탁금"))
print(f"레코드 수: {n}")
print(f"최상위 키(전체 통합): {sorted(keys)}")
print(f"거치식/적립식 안쪽 엔트리 키: {sorted(nested)}")
print(f"키워드 매치: {len(hits)}건")
for kw, s in hits[:20]:
    print(f"  [{kw}] {s}")

print("\n=== mg_dbanking_rates.jsonl ===")
n, keys, nested, hits = scan_jsonl(FIXTURES / "mg_dbanking_rates.jsonl")
print(f"레코드 수: {n}")
print(f"최상위 키(전체 통합): {sorted(keys)}")
print(f"키워드 매치: {len(hits)}건")
for kw, s in hits[:20]:
    print(f"  [{kw}] {s}")

print("\n=== kfcc_branches.json ===")
data = json.loads((FIXTURES / "kfcc_branches.json").read_text(encoding="utf-8"))
all_keys = set()
for b in data:
    all_keys |= set(b.keys())
print(f"레코드 수: {len(data)}")
print(f"키: {sorted(all_keys)}")
