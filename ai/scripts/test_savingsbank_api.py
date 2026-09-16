"""
저축은행(topFinGrpNo=030300) 정기예금 + 적금 데이터 수집.
기존 은행(020000) 데이터는 건드리지 않고 별도 파일로 저장한다.
"""
import json
import sys
import time
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import FSS_AUTH_KEY

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

TOP_FIN_GRP_NO = "030300"  # 저축은행

APIS = {
    "deposit": "https://finlife.fss.or.kr/finlifeapi/depositProductsSearch.json",
    "saving": "https://finlife.fss.or.kr/finlifeapi/savingProductsSearch.json",
}


def fetch_one(product_key, url):
    params = {"auth": FSS_AUTH_KEY, "topFinGrpNo": TOP_FIN_GRP_NO, "pageNo": "1"}
    res = requests.get(url, params=params, timeout=30)
    res.raise_for_status()
    data = res.json()
    result = data.get("result", {})

    print(f"[{product_key}] err_cd={result.get('err_cd')} total_count={result.get('total_count')}")

    out_path = FIXTURES_DIR / f"{product_key}_savingsbank_sample.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")


def main():
    if not FSS_AUTH_KEY:
        print("FSS_AUTH_KEY가 없습니다. .env를 확인하세요.")
        return

    for product_key, url in APIS.items():
        fetch_one(product_key, url)
        time.sleep(0.5)  # 연속 호출 사이 살짝 텀


if __name__ == "__main__":
    main()