"""새마을금고/농협 단위조합/수협 단위조합용 topFinGrpNo가 있는지 폭넓게 스캔."""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import FSS_AUTH_KEY

import requests

URL = "https://finlife.fss.or.kr/finlifeapi/depositProductsSearch.json"

CANDIDATES = [f"{i:06d}" for i in range(20000, 100000, 1000)]  # 020000 ~ 099000, 1000 단위

found_any = False
for code in CANDIDATES:
    params = {"auth": FSS_AUTH_KEY, "topFinGrpNo": code, "pageNo": 1}
    try:
        res = requests.get(URL, params=params, timeout=10)
        result = res.json().get("result", {})
        err_cd = result.get("err_cd")
        base_list = result.get("baseList", [])
    except Exception:
        continue

    if err_cd == "000" and base_list:
        found_any = True
        names = sorted({p.get("kor_co_nm") for p in base_list[:30]})
        keywords = [n for n in names if n and any(k in n for k in ["새마을", "농협", "수협"])]
        print(f"--- topFinGrpNo={code}: 상품 {len(base_list)}건 ---")
        print(f"  기관명 샘플: {names[:10]}")
        if keywords:
            print(f"  *** 관심 키워드 포함: {keywords} ***")
        print()

if not found_any:
    print("020000/030300/032000 외에 상품이 있는 코드가 없음")