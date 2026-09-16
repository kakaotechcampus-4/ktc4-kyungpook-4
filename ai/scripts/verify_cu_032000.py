"""신협조합(topFinGrpNo=032000)이 실제 FSS 정기예금/적금 API에서 동작하는지 확인."""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import FSS_AUTH_KEY

import requests

ENDPOINTS = {
    "정기예금": "https://finlife.fss.or.kr/finlifeapi/depositProductsSearch.json",
    "적금": "https://finlife.fss.or.kr/finlifeapi/savingProductsSearch.json",
}

for label, url in ENDPOINTS.items():
    print(f"=== {label} (topFinGrpNo=032000) ===")
    all_names = set()
    page = 1
    total = 0
    while True:
        params = {"auth": FSS_AUTH_KEY, "topFinGrpNo": "032000", "pageNo": page}
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        result = data.get("result", {})
        base_list = result.get("baseList", [])
        total += len(base_list)
        all_names.update(p.get("kor_co_nm") for p in base_list)
        max_page = result.get("max_page_no", 1)
        if page >= max_page or not base_list:
            break
        page += 1
    print(f"  총 상품 수: {total}")
    print(f"  조합 수(기관명 종류): {len(all_names)}")
    print(f"  기관명 샘플: {sorted(all_names)[:15]}")
    print()