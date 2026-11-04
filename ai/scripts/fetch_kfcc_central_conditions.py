"""
scripts/fetch_kfcc_central_conditions.py

새마을금고 중앙 금융상품몰(depositproduct.do)에서 예금/적금 상품 목록과
각 상품의 상세설명(우대이율 포함) 원문을 자동으로 수집해서
tests/fixtures/kfcc_central_conditions_raw.jsonl 로 저장한다.

사용법 (PowerShell):
    pip install requests beautifulsoup4
    python scripts/fetch_kfcc_central_conditions.py

나중에 새 상품이 추가되면 이 스크립트를 다시 실행하면 됨 -
목록(depositproduct.do)을 매번 새로 긁어오기 때문에 새 상품도 자동으로 포함됨.

[저장 방식 - 원자적 저장]
예전에는 상세를 못 받은 상품을 건너뛰고 저장했다. 그러면 빠진 상품이 run_pipeline 의 판매 종료
카운트에 +1 되고(이 소스는 "성공"이라서), 3주 연속이면 판매 종료로 처리될 수 있었다. 목록이 0건이어도
빈 파일로 덮어썼다. 이제는
  1단계: 목록과 상품별 상세를 전부 메모리에 받는다. 상세를 못 받은 상품은 끝에 한 번 더 시도한다.
  2단계: 목록 오류, 목록 0건, 재시도 후에도 상세를 못 받은 상품이 하나라도 있으면 실패 - 파일을 안 바꾼다.
  3단계: 임시 파일에 쓰고 원래 이름으로 바꾼다(os.replace).
(10/28 수집본: 상품 40개, 본문 빈 것 0개)
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://www.kfcc.co.kr"
LIST_URL = f"{BASE}/goods/depositproduct.do"
POPUP_URL_TMPL = f"{BASE}/html/goods/popup/{{goods_file}}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# 실행 위치와 상관없이 ai/tests/fixtures 에 저장한다 (예전엔 ai/ 에서 실행해야만 맞는 상대 경로였다)
OUT_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "kfcc_central_conditions_raw.jsonl"
TMP_PATH = OUT_PATH.with_name(OUT_PATH.name + ".tmp")


def fetch_catalog(section="1", max_pages=20):
    """depositproduct.do 목록 페이지를 pageNo=1부터 끝까지 순회하며
    {goods_file: product_name} 매핑을 전부 수집한다."""
    products = {}
    session = requests.Session()
    session.headers.update(HEADERS)

    for page_no in range(1, max_pages + 1):
        resp = session.post(
            LIST_URL,
            data={
                "pageNo": str(page_no),
                "section": section,
                "category": "",
                "seq": "",
                "order": "desc",
                "anc": "0",
                "hashtag": "",
            },
            timeout=15,
        )
        resp.raise_for_status()
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        spans = soup.select("span.prod_name[hidden]")
        if not spans:
            break  # 더 이상 상품이 없으면 종료

        found_new = False
        for span in spans:
            goods_file = span.get("id", "").strip()
            product_name = span.get_text(strip=True)
            if goods_file and goods_file not in products:
                products[goods_file] = product_name
                found_new = True

        print(f"[list] page {page_no}: {len(spans)}개 발견 (누적 {len(products)}개)")

        if not found_new:
            break  # 같은 목록 반복되면(마지막 페이지 넘어감) 종료

        time.sleep(0.5)  # 서버 부하 방지

    return products


def fetch_detail_text(session, goods_file):
    """상품 상세설명 팝업 페이지에서 본문 텍스트를 추출한다."""
    url = POPUP_URL_TMPL.format(goods_file=goods_file)
    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup(["script", "style"]):
        tag.decompose()

    # 본문 영역 후보(사이트 구조에 맞춰 필요시 조정)
    body = soup.select_one(".pop-body") or soup.select_one("#content") or soup.body
    text = body.get_text("\n", strip=True) if body else soup.get_text("\n", strip=True)
    text = re.sub(r"\n{2,}", "\n", text)
    return text, url


def _fail(reason):
    """파일을 바꾸지 않고 끝낸다(지난 수집본 유지)."""
    TMP_PATH.unlink(missing_ok=True)
    print(f"{reason} - 실패로 처리. 기존 수집본을 유지합니다.")
    sys.exit(1)


def _fetch_details(session, items, rows):
    """items 의 상세를 받아 rows[goods_file] 에 채운다. 실패한 (goods_file, 상품명) 목록을 돌려준다."""
    failed = []
    for goods_file, product_name in items:
        try:
            text, url = fetch_detail_text(session, goods_file)
        except requests.RequestException as e:
            print(f"  [실패] {product_name} ({goods_file}): {e}")
            failed.append((goods_file, product_name))
            continue
        rows[goods_file] = {
            "product_name": product_name,
            "goods_file": goods_file,
            "source_url": url,
            "spcl_cnd_raw": text,
            "fetched_date": time.strftime("%Y-%m-%d"),
        }
        print(f"  [완료] {product_name} ({goods_file}) - {len(text)}자")
        time.sleep(0.5)
    return failed


def main():
    print("=== 1) 상품 목록(카탈로그) 수집 ===")
    try:
        catalog = fetch_catalog()
    except requests.RequestException as e:
        _fail(f"상품 목록 수집 오류: {e}")
    print(f"총 {len(catalog)}개 상품 발견\n")
    if not catalog:
        _fail("상품 목록 0건")

    print("=== 2) 상품별 상세설명(우대이율 포함) 수집 ===")
    session = requests.Session()
    session.headers.update(HEADERS)

    rows = {}  # goods_file -> 저장할 행. 목록 순서를 지키려고 마지막에 목록 순서로 꺼낸다
    failed = _fetch_details(session, list(catalog.items()), rows)
    if failed:
        # 실패한 상품은 끝에 한 번 더 시도한다 (일시적인 오류일 수 있어서)
        print(f"\n상세 실패 {len(failed)}개 재시도")
        failed = _fetch_details(session, failed, rows)
    if failed:
        _fail(f"재시도 후에도 상세를 못 받은 상품 {len(failed)}개: {[name for _, name in failed]}")

    try:
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TMP_PATH.open("w", encoding="utf-8") as f:
            for goods_file in catalog:
                f.write(json.dumps(rows[goods_file], ensure_ascii=False) + "\n")
    except OSError as e:
        _fail(f"임시 파일 저장 실패: {e}")
    os.replace(TMP_PATH, OUT_PATH)

    print(f"\n총 {len(rows)}개 상품 저장 완료 -> {OUT_PATH}")


if __name__ == "__main__":
    main()