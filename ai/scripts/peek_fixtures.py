"""
tests/fixtures 아래 확정 사용 데이터 4개 파일의 실제 필드 구조 확인용.
ERD 매핑 스크립트를 짜기 전에 정확한 키 이름을 보기 위함.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
FILES = ["cu_rate_compare.jsonl", "kfcc_branches.json", "kfcc_rates.jsonl", "mg_dbanking_rates.jsonl"]


def main():
    for fname in FILES:
        p = ROOT / fname
        print(f"===== {fname} =====")
        if not p.exists():
            print("  파일 없음")
            print()
            continue
        if fname.endswith(".jsonl"):
            with p.open("r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= 2:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    print(" ", json.dumps(rec, ensure_ascii=False)[:500])
        else:
            data = json.loads(p.read_text(encoding="utf-8"))
            sample = data[:2] if isinstance(data, list) else data
            print(" ", json.dumps(sample, ensure_ascii=False)[:1000])
        print()


if __name__ == "__main__":
    main()