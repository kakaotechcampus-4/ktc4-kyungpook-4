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
"""
import json
import time
from pathlib import Path

import requests

OUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / "cu_rate_compare.jsonl"

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


def load_seen_keys() -> set[str]:
    """이미 저장된 (product_type, monTy) 조합은 재수집하지 않기 위한 재개용 체크."""
    seen = set()
    if OUT_PATH.exists():
        with OUT_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    seen.add(f"{rec['_product_type']}|{rec['_req_monTy']}")
                except Exception:
                    pass
    return seen


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
        return []
    return data


def main():
    session = requests.Session()
    # 목록 페이지를 먼저 한 번 방문해 세션 쿠키를 확보(브라우저 흐름 그대로 재현)
    for url in set(LIST_PAGE.values()):
        session.get(url, headers=HEADERS, timeout=20)

    done = load_seen_keys()
    print(f"이미 완료된 조합: {len(done)}개 (재개 모드)")

    total_saved = 0
    with OUT_PATH.open("a", encoding="utf-8") as out_f:
        for product_type in ("deposit", "savings"):
            for mon_ty in MONTY_LIST:
                key = f"{product_type}|{mon_ty}"
                if key in done:
                    print(f"[{product_type} / {mon_ty}개월] 이미 완료 - 건너뜀")
                    continue

                rows = fetch_one(session, product_type, mon_ty)
                for row in rows:
                    row["_product_type"] = product_type
                    row["_req_monTy"] = mon_ty
                    out_f.write(json.dumps(row, ensure_ascii=False) + "\n")

                total_now = rows[0]["listTotalCount"] if rows else 0
                print(f"[{product_type} / {mon_ty}개월] {len(rows)}건 수집 (listTotalCount={total_now})")
                total_saved += len(rows)
                time.sleep(0.5)

    print(f"\n이번 실행에서 새로 저장한 행 수: {total_saved} -> {OUT_PATH}")


if __name__ == "__main__":
    main()