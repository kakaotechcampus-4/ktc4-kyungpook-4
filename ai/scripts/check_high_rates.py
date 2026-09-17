"""
cu_rate_compare.jsonl 안에 "특판급"으로 볼만한 고금리(예: 4% 이상)가
실제로 얼마나, 어떤 조합/상품에서 잡히는지 확인.
- 블로거가 봤다는 "신협 4.7%" 같은 특판이 이 공식 공시 데이터에도
  등장하는지를 직접 눈으로 확인하기 위한 스크립트.
"""
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
PATH = FIXTURES_DIR / "cu_rate_compare.jsonl"

THRESHOLD = 4.0  # 이 이상이면 "특판급 고금리"로 간주


def parse_pct(s: str) -> float:
    try:
        return float(str(s).replace("%", "").strip())
    except Exception:
        return -1.0


def main():
    records = []
    with PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    # highRate(우대후 최고금리) 기준 내림차순 정렬
    for r in records:
        r["_highRate_num"] = parse_pct(r.get("highRate", ""))

    records.sort(key=lambda r: r["_highRate_num"], reverse=True)

    high = [r for r in records if r["_highRate_num"] >= THRESHOLD]
    print(f"전체 {len(records)}건 중 highRate {THRESHOLD}% 이상: {len(high)}건 ({len(high)/len(records)*100:.2f}%)")

    print(f"\n=== highRate 상위 20건 ===")
    for r in records[:20]:
        print(
            f"  {r.get('cuNm')} | {r.get('stockNm')} | {r.get('_req_monTy')}개월 | "
            f"기본 {r.get('baseRate')} / 최고 {r.get('highRate')} | 가입방법: {r.get('tretYn')} | "
            f"공시일: {r.get('pubiBeginDate')}"
        )

    # 최고금리 분포 요약(구간별 건수)
    buckets = {"~2%": 0, "2~3%": 0, "3~4%": 0, "4~5%": 0, "5%+": 0}
    for r in records:
        v = r["_highRate_num"]
        if v < 2:
            buckets["~2%"] += 1
        elif v < 3:
            buckets["2~3%"] += 1
        elif v < 4:
            buckets["3~4%"] += 1
        elif v < 5:
            buckets["4~5%"] += 1
        else:
            buckets["5%+"] += 1
    print(f"\n=== highRate 구간별 분포 ===")
    for k, v in buckets.items():
        print(f"  {k}: {v}건 ({v/len(records)*100:.1f}%)")


if __name__ == "__main__":
    main()