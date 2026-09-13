"""
새마을금고 지점별 실제 금리 수집 (fetch_kfcc_branches.py 결과물이 먼저 있어야 함).

브라우저 네트워크 탭으로 실제 확인한 요청:
  POST https://www.kfcc.co.kr/map/goods_19.do
  body: tabInfo=&OPEN_TRMID=<gmgoCd>&gubuncode=13   -> 거치식예탁금(정기예금 격)
  body: tabInfo=&OPEN_TRMID=<gmgoCd>&gubuncode=14   -> 적립식예탁금(적금 격)

지점 수가 많으므로(전국 약 3천개+) 중간에 끊겨도 이어할 수 있도록
결과를 JSONL로 한 줄씩 즉시 저장하고, 이미 처리한 gmgoCd는 재실행 시 건너뜀.
"""
import json
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
BRANCHES_PATH = FIXTURES_DIR / "kfcc_branches.json"
OUT_PATH = FIXTURES_DIR / "kfcc_rates.jsonl"

RATE_URL = "https://www.kfcc.co.kr/map/goods_19.do"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.kfcc.co.kr/map/main.do",
}

GUBUN = {"13": "거치식예탁금", "14": "적립식예탁금"}


def parse_products(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    products = []
    for wrap in soup.select(".tblWrap"):
        title_el = wrap.select_one(".tbl-tit")
        title = title_el.get_text(strip=True) if title_el else None
        table = wrap.select_one("table")
        if not table:
            continue
        headers = [th.get_text(strip=True) for th in table.select("thead th")]
        rows = []
        for tr in table.select("tbody tr"):
            cells = [td.get_text(strip=True) for td in tr.select("td")]
            if cells:
                rows.append(cells)
        if rows:
            products.append({"product_title": title, "headers": headers, "rows": rows})
    return products


def fetch_rate(session: requests.Session, gmgo_cd: str, gubuncode: str) -> list[dict]:
    resp = session.post(
        RATE_URL,
        data={"tabInfo": "", "OPEN_TRMID": gmgo_cd, "gubuncode": gubuncode},
        headers=HEADERS,
        timeout=20,
    )
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return parse_products(resp.text)


def load_done_codes() -> set[str]:
    done = set()
    if OUT_PATH.exists():
        with OUT_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    done.add(rec["gmgoCd"])
                except Exception:
                    pass
    return done


def main():
    if not BRANCHES_PATH.exists():
        print(f"{BRANCHES_PATH} 가 없습니다. fetch_kfcc_branches.py 를 먼저 실행하세요.")
        return

    branches = json.loads(BRANCHES_PATH.read_text(encoding="utf-8"))
    unique_codes = {}
    for b in branches:
        code = b.get("gmgoCd")
        if code and code not in unique_codes:
            unique_codes[code] = b

    already_done = load_done_codes()
    todo = [c for c in unique_codes if c not in already_done]
    print(f"전체 지점 {len(unique_codes)}개, 이미 완료 {len(already_done)}개, 남은 {len(todo)}개")

    session = requests.Session()
    session.get("https://www.kfcc.co.kr/map/main.do", headers=HEADERS, timeout=20)

    with OUT_PATH.open("a", encoding="utf-8") as out_f:
        for i, code in enumerate(todo, 1):
            branch = unique_codes[code]
            rec = {"gmgoCd": code, "gmgoNm": branch.get("gmgoNm"), "divNm": branch.get("divNm"),
                   "r1": branch.get("r1"), "r2": branch.get("r2")}
            for gubuncode, label in GUBUN.items():
                try:
                    products = fetch_rate(session, code, gubuncode)
                except Exception as e:
                    print(f"  [{i}/{len(todo)}] {branch.get('gmgoNm')} {label} 실패: {e}")
                    products = None
                rec[label] = products
                time.sleep(0.25)

            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out_f.flush()

            if i % 20 == 0 or i == len(todo):
                print(f"  [{i}/{len(todo)}] {branch.get('gmgoNm')} ({branch.get('r1')} {branch.get('r2')}) 완료")

    print(f"\n저장 완료 -> {OUT_PATH}")


if __name__ == "__main__":
    main()