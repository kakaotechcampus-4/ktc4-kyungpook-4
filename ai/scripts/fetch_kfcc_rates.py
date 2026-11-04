"""
새마을금고 지점별 실제 금리 수집 (fetch_kfcc_branches.py 결과물이 먼저 있어야 함).

브라우저 네트워크 탭으로 실제 확인한 요청:
  POST https://www.kfcc.co.kr/map/goods_19.do
  body: tabInfo=&OPEN_TRMID=<gmgoCd>&gubuncode=13   -> 거치식예탁금(정기예금 격)
  body: tabInfo=&OPEN_TRMID=<gmgoCd>&gubuncode=14   -> 적립식예탁금(적금 격)

[저장 방식 - 매번 전체 수집 + 지점 목록과 한 묶음으로 교체]
예전에는 시작하자마자 기존 파일을 지우고(--refresh) 지점마다 한 줄씩 덧붙였다. 그러면 중간에 사이트가
막히면 지난 수집본은 이미 지워졌고 반쪽 파일만 남았다. 지점 대부분이 실패해도 종료 코드 0 이었다.
이제는
  1단계: 전체 지점(약 1천 곳 x 2구분)을 메모리에 받는다. 실패한 지점은 끝에 한 번 더 시도한다.
  2단계: 재시도 후에도 실패한 지점이 1%를 넘으면 사이트 문제로 보고 실패 처리 - 파일을 하나도 안 바꾼다.
         (10/28 수집본: 1,037곳 중 3곳 실패 = 0.3%. 1% 이하로 남은 실패 지점은 지금처럼 None 으로 적고,
          build_erd_tables.py 가 경고로 보여준다)
  3단계: 임시 파일에 쓰고, 지점 목록 .next 가 있으면 두 파일을 함께 원래 이름으로 바꾼다(os.replace).
지점 목록은 fetch_kfcc_branches.py 가 kfcc_branches.json.next 에 둔 새 수집본을 쓴다. .next 가 없으면
(이 스크립트만 따로 돌릴 때) 지금 kfcc_branches.json 을 쓰고 금리 파일만 바꾼다.
실패하면 .next 를 지운다 - 지점 목록과 금리 모두 지난 수집본을 유지해 서로 다른 주 데이터가 섞이지 않는다.
연속으로 CONSECUTIVE_FAIL_LIMIT 곳이 실패하면 사이트가 막힌 것으로 보고 바로 중단한다
(남은 지점을 다 돌아도 1%를 넘어 어차피 실패이므로, 막힌 주에 시간을 쓰지 않으려고).
"""
import json
import os
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
BRANCHES_PATH = FIXTURES_DIR / "kfcc_branches.json"
# fetch_kfcc_branches.py 가 저장한 새 지점 목록. 금리까지 성공하면 BRANCHES_PATH 로 옮긴다
BRANCHES_NEXT_PATH = FIXTURES_DIR / "kfcc_branches.json.next"
OUT_PATH = FIXTURES_DIR / "kfcc_rates.jsonl"
TMP_PATH = FIXTURES_DIR / "kfcc_rates.jsonl.tmp"

# 재시도 후에도 실패한 지점이 이 비율을 넘으면 전체 실패
MAX_FAILED_RATIO = 0.01
# 연속으로 이만큼 실패하면 사이트가 막힌 것으로 보고 즉시 중단
CONSECUTIVE_FAIL_LIMIT = 20

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


def _fail(reason):
    """파일을 하나도 바꾸지 않고 끝낸다. 새 지점 목록(.next)도 지워 지점 목록·금리 모두 지난 수집본을 유지한다."""
    TMP_PATH.unlink(missing_ok=True)
    BRANCHES_NEXT_PATH.unlink(missing_ok=True)
    print(f"{reason} - 실패로 처리. 지점 목록·금리 모두 기존 수집본을 유지합니다.")
    sys.exit(1)


def fetch_branch(session: requests.Session, rec: dict) -> bool:
    """rec 에 거치식/적립식 금리를 채운다. 실패한 구분은 None. 하나라도 실패하면 False."""
    ok = True
    for gubuncode, label in GUBUN.items():
        if rec.get(label) is not None:
            continue  # 재시도 때 이미 받은 구분은 다시 받지 않는다
        try:
            rec[label] = fetch_rate(session, rec["gmgoCd"], gubuncode)
        except requests.RequestException as e:
            print(f"  {rec.get('gmgoNm')} {label} 실패: {e}")
            rec[label] = None
            ok = False
        time.sleep(0.25)
    return ok


def main():
    branches_path = BRANCHES_NEXT_PATH if BRANCHES_NEXT_PATH.exists() else BRANCHES_PATH
    if not branches_path.exists():
        _fail(f"{BRANCHES_PATH} 가 없습니다. fetch_kfcc_branches.py 를 먼저 실행하세요")
    print(f"지점 목록: {branches_path.name}")

    branches = json.loads(branches_path.read_text(encoding="utf-8"))
    unique_codes = {}
    for b in branches:
        code = b.get("gmgoCd")
        if code and code not in unique_codes:
            unique_codes[code] = b
    if not unique_codes:
        _fail("지점 목록이 비어 있음")
    print(f"전체 지점 {len(unique_codes)}개")

    session = requests.Session()
    try:
        session.get("https://www.kfcc.co.kr/map/main.do", headers=HEADERS, timeout=20)
    except requests.RequestException as e:
        _fail(f"메인 페이지 접속 오류: {e}")

    # 1단계: 전체 지점 받기 - 이 단계에서는 파일을 건드리지 않는다
    records = []
    failed = []  # 한 구분이라도 실패한 지점의 rec
    consecutive = 0
    for i, (code, branch) in enumerate(unique_codes.items(), 1):
        rec = {"gmgoCd": code, "gmgoNm": branch.get("gmgoNm"), "divNm": branch.get("divNm"),
               "r1": branch.get("r1"), "r2": branch.get("r2")}
        for label in GUBUN.values():
            rec[label] = None
        if fetch_branch(session, rec):
            consecutive = 0
        else:
            failed.append(rec)
            consecutive += 1
            if consecutive >= CONSECUTIVE_FAIL_LIMIT:
                _fail(f"{consecutive}곳 연속 실패 ({i}/{len(unique_codes)}번째에서 중단) - 사이트가 막힌 것으로 판단")
        records.append(rec)
        if i % 20 == 0 or i == len(unique_codes):
            print(f"  [{i}/{len(unique_codes)}] {branch.get('gmgoNm')} ({branch.get('r1')} {branch.get('r2')}) 완료")

    # 실패한 지점은 끝에 한 번 더 시도한다 (일시적인 오류일 수 있어서)
    if failed:
        print(f"\n실패한 지점 {len(failed)}곳 재시도")
    still_failed = [rec for rec in failed if not fetch_branch(session, rec)]

    # 2단계: 남은 실패가 1%를 넘으면 전체 실패
    limit = len(unique_codes) * MAX_FAILED_RATIO
    print(f"재시도 후 실패 지점 {len(still_failed)}곳 (허용 {limit:.1f}곳 이하)")
    if len(still_failed) > limit:
        names = [rec.get("gmgoNm") for rec in still_failed[:10]]
        _fail(f"실패 지점이 1%를 넘음 ({len(still_failed)}/{len(unique_codes)}곳, 예: {names})")

    # 3단계: 임시 파일에 쓰고, 지점 목록과 함께 한 번에 교체
    try:
        with TMP_PATH.open("w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as e:
        _fail(f"임시 파일 저장 실패: {e}")
    if branches_path == BRANCHES_NEXT_PATH:
        os.replace(BRANCHES_NEXT_PATH, BRANCHES_PATH)
        print(f"지점 목록 교체 완료 -> {BRANCHES_PATH}")
    os.replace(TMP_PATH, OUT_PATH)
    print(f"\n금리 저장 완료 ({len(records)}곳, 실패로 비워 둔 지점 {len(still_failed)}곳) -> {OUT_PATH}")


if __name__ == "__main__":
    main()
