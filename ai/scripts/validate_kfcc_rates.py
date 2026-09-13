"""
kfcc_rates.jsonl 품질 점검: 1,039개 지점 x 2종(거치식/적립식) 파싱이
실제로 잘 됐는지 확인. products가 null(요청 실패)이거나 빈 리스트([], 표를 못찾음)인
지점 비율을 세고, 정상 샘플 몇 개를 출력한다.
"""
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
PATH = FIXTURES_DIR / "kfcc_rates.jsonl"

LABELS = ["거치식예탁금", "적립식예탁금"]


def main():
    records = []
    with PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    print(f"총 레코드 수: {len(records)}")

    for label in LABELS:
        null_cnt = sum(1 for r in records if r.get(label) is None)
        empty_cnt = sum(1 for r in records if r.get(label) == [])
        ok_cnt = len(records) - null_cnt - empty_cnt
        print(f"\n[{label}]")
        print(f"  요청 실패(null): {null_cnt}건")
        print(f"  표 없음(빈 리스트): {empty_cnt}건")
        print(f"  정상 파싱: {ok_cnt}건 ({ok_cnt/len(records)*100:.1f}%)")

    print("\n=== 정상 파싱 샘플 3개 ===")
    shown = 0
    for r in records:
        if r.get("거치식예탁금"):
            print(f"\n지점: {r.get('gmgoNm')} ({r.get('r1')} {r.get('r2')}, {r.get('divNm')})")
            for prod in r["거치식예탁금"][:2]:
                print(f"  상품: {prod.get('product_title')}")
                print(f"    헤더: {prod.get('headers')}")
                for row in prod.get("rows", [])[:3]:
                    print(f"    {row}")
            shown += 1
            if shown >= 3:
                break

    empties = [r for r in records if r.get("거치식예탁금") == []]
    if empties:
        print(f"\n=== 거치식예탁금 빈 리스트 지점 샘플 3개 (gmgoCd로 원인 추적용) ===")
        for r in empties[:3]:
            print(f"  {r.get('gmgoCd')} {r.get('gmgoNm')} ({r.get('r1')} {r.get('r2')})")


if __name__ == "__main__":
    main()