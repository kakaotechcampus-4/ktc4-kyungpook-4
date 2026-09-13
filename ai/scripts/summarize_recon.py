"""
nh_rate_page_recon.jsonl / suhyup_rate_page_recon.jsonl 정찰 결과 요약.
- 링크를 찾았는지 / 못 찾았는지 비율
- 에러 종류별 건수
- 표 헤더(sample_header) 시그니처별 건수 상위 N개 -> 이게 곧 "CMS 패턴이 몇 종류인지"를 보여줌
"""
import json
from collections import Counter
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def summarize(path: Path):
    if not path.exists():
        print(f"{path.name} 없음 - 건너뜀")
        return

    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    print(f"\n{'='*20} {path.name} {'='*20}")
    print(f"총 처리: {len(records)}건")

    errors = [r for r in records if "error" in r]
    print(f"에러: {len(errors)}건")
    if errors:
        err_types = Counter(e["error"][:60] for e in errors)
        print("  에러 유형 상위 5개:")
        for msg, cnt in err_types.most_common(5):
            print(f"    {cnt}건: {msg}")

    ok = [r for r in records if "error" not in r]
    found = [r for r in ok if r.get("rate_link_found")]
    not_found = [r for r in ok if not r.get("rate_link_found")]
    print(f"금리 메뉴 링크 발견: {len(found)}건 / 못 찾음: {len(not_found)}건")

    with_table = [r for r in found if (r.get("table_count") or 0) > 0]
    print(f"  -> 그 중 표(table)가 실제로 있었던 경우: {len(with_table)}건")

    def sig_key(r):
        h = r.get("sample_header") or []
        return (len(h), tuple(h))

    sigs = Counter(sig_key(r) for r in with_table)
    print(f"\n표 헤더 시그니처(칸 수, 헤더 내용)별 건수 - 상위 15개:")
    for (n, header), cnt in sigs.most_common(15):
        print(f"  {cnt}건 | {n}칸 | {header}")


def main():
    summarize(FIXTURES_DIR / "nh_rate_page_recon.jsonl")
    summarize(FIXTURES_DIR / "suhyup_rate_page_recon.jsonl")


if __name__ == "__main__":
    main()