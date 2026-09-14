"""
cu_rate_compare.jsonl 품질 점검:
- 총 행 수 / product_type x monTy 별 건수
- 대면/비대면 비율(stockNm 끝 "(대면)"/"(비대면)" 기준)
- 조합(cuIngno) 커버리지(전체 신협 조합 수와 대략 비교)
- 정상 샘플 몇 개 출력
"""
import json
from collections import Counter
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
PATH = FIXTURES_DIR / "cu_rate_compare.jsonl"


def main():
    records = []
    with PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    print(f"총 레코드 수: {len(records)}")

    by_key = Counter((r.get("_product_type"), r.get("_req_monTy")) for r in records)
    print("\n=== product_type x monTy 별 건수 ===")
    for (pt, mt), cnt in sorted(by_key.items()):
        print(f"  {pt} / {mt}개월: {cnt}건")

    def channel(r):
        name = r.get("stockNm", "")
        if "(비대면)" in name:
            return "비대면"
        if "(대면)" in name:
            return "대면"
        return "기타(표시없음)"

    channel_cnt = Counter(channel(r) for r in records)
    print("\n=== 대면/비대면 분포 ===")
    for k, v in channel_cnt.items():
        print(f"  {k}: {v}건 ({v/len(records)*100:.1f}%)")

    cuIngno_set = {r.get("cuIngno") for r in records}
    print(f"\n등장하는 조합 수(cuIngno 기준, 중복제거): {len(cuIngno_set)}")

    print("\n=== 정상 샘플 5개 ===")
    for r in records[:5]:
        print(
            f"  {r.get('cuNm')} | {r.get('stockNm')} | {r.get('_req_monTy')}개월 | "
            f"기본 {r.get('baseRate')} / 최고 {r.get('highRate')} | 가입방법: {r.get('tretYn')} | "
            f"공시일: {r.get('pubiBeginDate')}"
        )


if __name__ == "__main__":
    main()