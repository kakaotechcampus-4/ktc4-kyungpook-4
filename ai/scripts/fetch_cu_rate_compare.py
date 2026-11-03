"""
신협(cu.co.kr) "예금 금리비교" 전자공시 시스템 수집.

브라우저에서 네트워크 요청을 직접 잡아서 확인한 실제 엔드포인트:

  거치식예금(정기예탁금): POST /cu/ad/inrstCmpr/findInrst15CmprListResult.do
  적립식예금(정기적금) : POST /cu/ad/inrstCmpr/findInrst17CmprListResult.do

  body(둘 다 동일한 필드):
    currPage, listMaxCnt, highLimtAmt, monTy, sido, subSido,
    tretChlTy, sortColumn, sortAsc, searchTxt

핵심 확인 사항:
- tretChlTy(가입방식: 1=창구,2=인터넷,3=모바일)를 "A"(전체)로 주면
  대면/비대면이 한 번에 다 나오고, 각 행의 tretYn(가입방법)과
  stockNm 끝의 "(대면)"/"(비대면)" 표시로 구분 가능함
  -> 굳이 채널별로 3번 나눠 부를 필요 없음.
- highLimtAmt(저축금액)는 결과에 전혀 영향 없음(같은 monTy면 금액 달라도
  동일한 rows) -> 아무 값이나 고정해도 됨.
- monTy(저축예정기간)는 실제로 결과를 크게 바꿈(01/03/06/12/24/36개월
  6종류, 버튼으로 확인) -> 6번 다 순회해야 전체를 얻음.
- listMaxCnt에 사실상 상한이 없음(10000을 줘도 전부 한 번에 반환됨,
  화면상 select는 10/20/50뿐이지만 서버는 더 큰 값도 받아줌)
  -> product_type(2종) x monTy(6종) = 총 12번 요청이면 전체 수집 끝남.

[저장 방식 - 매번 전체 새로 받기 + 원자적 저장]
예전에는 이미 파일에 있는 조합을 건너뛰는 "재개 모드"였다. GitHub Actions 는 매번 빈 상태로
시작해서 문제가 없었지만, 디스크가 남는 서버(EC2)에서는 둘째 주부터 12개 조합을 전부 건너뛰어
신협 데이터가 첫 수집본으로 멈춘다(그래도 성공으로 끝나 아무도 모름). 그래서 재개 모드를 없앴다.
12번 요청이라 매번 전부 받아도 오래 걸리지 않는다.
  1단계: 12개 조합을 전부 메모리에 받는다. 하나라도 실패하면 파일을 건드리지 않고 종료 코드 1.
  2단계: 임시 파일(*.tmp)에 쓴다. 쓰다가 실패하면 임시 파일만 지우고 종료 코드 1.
  3단계: 원래 이름으로 바꾼다(os.replace). 이 단계는 순식간에 끝난다.
실패로 보는 경우: 요청 오류(네트워크·HTTP 오류), 응답이 목록(JSON 배열)이 아닐 때, 0건 수집,
서버가 알려준 전체 건수와 실제로 받은 건수가 다를 때.
전체 건수(listTotalCount)는 일부 행에만 들어 있고 나머지 행은 0이라 조합 안의 가장 큰 값을 쓴다.
(2026-09-22 수집본 확인: 12개 조합 모두 0건 없음, 가장 큰 listTotalCount = 행 수)
"""
import json
import os
import sys
import time
from pathlib import Path

import requests

OUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / "cu_rate_compare.jsonl"
TMP_PATH = OUT_DIR / "cu_rate_compare.jsonl.tmp"

BASE = "https://www.cu.co.kr"
LIST_PAGE = {
    "deposit": f"{BASE}/cu/ad/inrstCmpr/findInrst15CmprList.do?mi=201001",   # 거치식예금(정기예탁금)
    "savings": f"{BASE}/cu/ad/inrstCmpr/findInrst17CmprList.do?mi=201002",  # 적립식예금(정기적금)
}
RESULT_URL = {
    "deposit": f"{BASE}/cu/ad/inrstCmpr/findInrst15CmprListResult.do",
    "savings": f"{BASE}/cu/ad/inrstCmpr/findInrst17CmprListResult.do",
}
MONTY_LIST = ["01", "03", "06", "12", "24", "36"]  # 1/3/6/12/24/36개월

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}


class FetchError(Exception):
    """응답이 목록이 아니거나 받은 데이터가 온전하지 않을 때."""


def _fail(label, reason):
    """하나라도 실패하면 파일을 바꾸지 않고 끝낸다(지난 수집본 그대로 유지)."""
    print(f"[{label}] {reason} - 실패로 처리. 기존 수집본을 유지합니다.")
    sys.exit(1)


def fetch_one(session: requests.Session, product_type: str, mon_ty: str) -> list[dict]:
    resp = session.post(
        RESULT_URL[product_type],
        data={
            "currPage": "1",
            "listMaxCnt": "20000",
            "highLimtAmt": "10,000,000",
            "monTy": mon_ty,
            "sido": "AA",
            "subSido": "AA",
            "tretChlTy": "A",
            "sortColumn": "CU_NM",
            "sortAsc": "A",
            "searchTxt": "",
        },
        headers={**HEADERS, "Referer": LIST_PAGE[product_type]},
        timeout=30,
    )
    resp.raise_for_status()
    resp.encoding = "utf-8"
    data = resp.json()
    if not isinstance(data, list):
        # 예전에는 0건으로 넘어갔다. 사이트가 오류 응답을 줘도 그 조합이 통째로 비는 걸 막는다
        raise FetchError(f"응답이 목록이 아님 (type={type(data).__name__})")
    return data


def reported_total(rows: list[dict]) -> int:
    """서버가 알려준 전체 건수. 일부 행에만 들어 있고 나머지는 0이라 가장 큰 값을 쓴다."""
    return max(int(row.get("listTotalCount") or 0) for row in rows)


def main():
    session = requests.Session()
    # 목록 페이지를 먼저 한 번 방문해 세션 쿠키를 확보(브라우저 흐름 그대로 재현)
    try:
        for url in set(LIST_PAGE.values()):
            session.get(url, headers=HEADERS, timeout=20)
    except requests.RequestException as e:
        _fail("목록 페이지", f"접속 오류: {e}")

    # 1단계: 12개 조합 전부 받기 - 이 단계에서는 파일을 건드리지 않는다
    collected = []
    for product_type in ("deposit", "savings"):
        for mon_ty in MONTY_LIST:
            label = f"{product_type} / {mon_ty}개월"
            try:
                rows = fetch_one(session, product_type, mon_ty)
            except (requests.RequestException, ValueError, FetchError) as e:  # 네트워크·HTTP 오류, JSON 아님, 목록 아님
                _fail(label, f"수집 중 오류: {e}")
            if not rows:
                _fail(label, "0건 수집")
            try:
                total = reported_total(rows)
            except (TypeError, ValueError) as e:
                _fail(label, f"listTotalCount 를 읽을 수 없음: {e}")
            print(f"[{label}] {len(rows)}건 수집 (listTotalCount={total})")
            if total != len(rows):
                _fail(label, f"건수 불일치 (서버 보고 {total}건, 실제 {len(rows)}건)")
            for row in rows:
                row["_product_type"] = product_type
                row["_req_monTy"] = mon_ty
            collected.extend(rows)
            time.sleep(0.5)

    # 2단계: 임시 파일에 쓰기 - 실패하면 임시 파일만 지우고 원본은 그대로 둔다
    try:
        with TMP_PATH.open("w", encoding="utf-8") as f:
            for row in collected:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as e:
        TMP_PATH.unlink(missing_ok=True)
        print(f"임시 파일 저장 실패: {e} - 기존 수집본을 유지합니다.")
        sys.exit(1)

    # 3단계: 한 번에 원래 이름으로 교체
    os.replace(TMP_PATH, OUT_PATH)
    print(f"\n12개 조합 모두 수집 성공 - 총 {len(collected)}행 저장 완료 -> {OUT_PATH}")


if __name__ == "__main__":
    main()
