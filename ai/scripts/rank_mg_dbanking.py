"""
kfcc_rates.jsonl 안에서 "MG더뱅킹*" (정기예금/정기적금/자유적금 등) 상품만 뽑아서
mgija.com 식 "계약기간별 최고금리 랭킹"을 우리 원본 데이터로 직접 만든다.

파싱 시 주의사항(peek_mg_dbanking.py로 확인한 실제 구조):
- headers = ["상품명","계약기간","기본이율"] 이지만
  원본 HTML 표에서 "상품명" 칸이 rowspan으로 병합돼 있어서
  첫 행만 3칸([상품명,계약기간,금리])이고 나머지 행은 2칸([계약기간,금리])임.
  -> 행 길이로 분기해서 파싱해야 함.
- "연0.0%"으로 나오는 행은 그 계약기간에는 상품을 안 판다는 뜻(최소가입기간 미달)
  으로 보임 -> 랭킹에서는 제외.

결과물:
- tests/fixtures/mg_dbanking_rates.jsonl : 지점 x 상품 x 계약기간 단위로 펼친 전체 데이터
- 화면 출력: 계약기간(3/6/12개월)별 정기예금·정기적금 최고금리 TOP 10
"""
import json
import re
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
IN_PATH = FIXTURES_DIR / "kfcc_rates.jsonl"
OUT_PATH = FIXTURES_DIR / "mg_dbanking_rates.jsonl"

LABELS = ["거치식예탁금", "적립식예탁금"]


def parse_rate(s: str) -> float | None:
    m = re.search(r"([\d.]+)\s*%", s or "")
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def parse_term_months(s: str) -> int | None:
    m = re.search(r"(\d+)\s*개월", s or "")
    if not m:
        return None
    return int(m.group(1))


def extract_rows(prod: dict) -> list[tuple[str, str, float]]:
    """(term_raw, rate_raw, rate_num) 튜플 리스트. 상품명 rowspan 때문에
    행 길이가 3이면 [상품명,기간,금리], 2면 [기간,금리]로 처리."""
    out = []
    for row in prod.get("rows", []):
        if len(row) >= 3:
            term_raw, rate_raw = row[1], row[2]
        elif len(row) == 2:
            term_raw, rate_raw = row[0], row[1]
        else:
            continue
        rate_num = parse_rate(rate_raw)
        if rate_num is None:
            continue
        out.append((term_raw, rate_raw, rate_num))
    return out


def main():
    flat = []
    with IN_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            for label in LABELS:
                for prod in rec.get(label) or []:
                    title = prod.get("product_title", "")
                    if "MG더뱅킹" not in title:
                        continue
                    for term_raw, rate_raw, rate_num in extract_rows(prod):
                        if rate_num <= 0:
                            continue  # 미취급 계약기간
                        flat.append({
                            "gmgoCd": rec.get("gmgoCd"),
                            "gmgoNm": rec.get("gmgoNm"),
                            "r1": rec.get("r1"),
                            "r2": rec.get("r2"),
                            "divNm": rec.get("divNm"),
                            "category": label,
                            "product_title": title,
                            "term_raw": term_raw,
                            "term_months": parse_term_months(term_raw),
                            "rate": rate_num,
                        })

    with OUT_PATH.open("w", encoding="utf-8") as out_f:
        for row in flat:
            out_f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"총 {len(flat)}건 추출 -> {OUT_PATH}")

    # product_title 종류별 건수
    titles = {}
    for row in flat:
        titles[row["product_title"]] = titles.get(row["product_title"], 0) + 1
    print("\n=== 상품명별 건수 ===")
    for t, c in sorted(titles.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}건")

    # 계약기간별 최고금리 TOP 10 (정기예금/정기적금 각각)
    for title_filter, label_kr in [("MG더뱅킹정기예금", "정기예금"), ("MG더뱅킹정기적금", "정기적금")]:
        subset = [r for r in flat if r["product_title"] == title_filter]
        months_present = sorted({r["term_months"] for r in subset if r["term_months"] is not None})
        for months in months_present:
            term_rows = [r for r in subset if r["term_months"] == months]
            term_rows.sort(key=lambda r: r["rate"], reverse=True)
            print(f"\n=== {label_kr} {months}개월 이상 최고금리 TOP 10 (전체 {len(term_rows)}개 지점) ===")
            for r in term_rows[:10]:
                print(f"  {r['gmgoNm']} ({r['r1']} {r['r2']}) | {r['rate']}%")


if __name__ == "__main__":
    main()