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
"""

import json
import re
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

OUT_PATH = Path("tests/fixtures/kfcc_central_conditions_raw.jsonl")


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


def main():
    print("=== 1) 상품 목록(카탈로그) 수집 ===")
    catalog = fetch_catalog()
    print(f"총 {len(catalog)}개 상품 발견\n")

    print("=== 2) 상품별 상세설명(우대이율 포함) 수집 ===")
    session = requests.Session()
    session.headers.update(HEADERS)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for goods_file, product_name in catalog.items():
        try:
            text, url = fetch_detail_text(session, goods_file)
        except Exception as e:
            print(f"  [실패] {product_name} ({goods_file}): {e}")
            continue

        rows.append(
            {
                "product_name": product_name,
                "goods_file": goods_file,
                "source_url": url,
                "spcl_cnd_raw": text,
                "fetched_date": time.strftime("%Y-%m-%d"),
            }
        )
        print(f"  [완료] {product_name} ({goods_file}) - {len(text)}자")
        time.sleep(0.5)

    with OUT_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\n총 {len(rows)}개 상품 저장 완료 -> {OUT_PATH}")


if __name__ == "__main__":
    main()