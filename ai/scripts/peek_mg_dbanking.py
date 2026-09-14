"""
kfcc_rates.jsonl 안에서 "MG더뱅킹" 이름이 붙은 상품 하나를 실제로 뽑아서
headers/rows 구조가 어떻게 생겼는지 그대로 출력.
-> 이 구조를 보고 나서 "지점별 MG더뱅킹 최고금리 랭킹" 스크립트를 정확히 짜기 위함.
"""
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
PATH = FIXTURES_DIR / "kfcc_rates.jsonl"

LABELS = ["거치식예탁금", "적립식예탁금"]


def main():
    shown = 0
    with PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            for label in LABELS:
                products = rec.get(label) or []
                for prod in products:
                    title = prod.get("product_title", "")
                    if "MG더뱅킹" in title:
                        print(f"=== 지점: {rec.get('gmgoNm')} ({rec.get('gmgoCd')}) | 구분: {label} ===")
                        print(json.dumps(prod, ensure_ascii=False, indent=2))
                        print()
                        shown += 1
                        if shown >= 3:
                            return


if __name__ == "__main__":
    main()