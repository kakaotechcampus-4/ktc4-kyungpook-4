"""신협 spcl_cnd 필드에 실제로 뭐가 들어있는지 확인 (길이 분포 + 샘플)."""
import sys
from pathlib import Path
from collections import Counter

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import FSS_AUTH_KEY

import requests

URL = "https://finlife.fss.or.kr/finlifeapi/depositProductsSearch.json"

base_list = []
page = 1
while True:
    params = {"auth": FSS_AUTH_KEY, "topFinGrpNo": "032000", "pageNo": page}
    res = requests.get(URL, params=params, timeout=10)
    result = res.json().get("result", {})
    base_list.extend(result.get("baseList", []))
    max_page = result.get("max_page_no", 1)
    if page >= max_page or page > 15:
        break
    page += 1

print(f"총 수집: {len(base_list)}건\n")

lengths = [len(p.get("spcl_cnd", "") or "") for p in base_list]
buckets = Counter()
for l in lengths:
    if l == 0:
        buckets["0(공백)"] += 1
    elif l < 10:
        buckets["1~9자"] += 1
    elif l < 20:
        buckets["10~19자"] += 1
    elif l < 50:
        buckets["20~49자"] += 1
    else:
        buckets["50자 이상"] += 1

print("spcl_cnd 길이 분포:")
for k, v in buckets.items():
    print(f"  {k}: {v}건")

print("\n비어있지 않은 spcl_cnd 샘플 10개:")
non_empty = [p for p in base_list if p.get("spcl_cnd")]
for p in non_empty[:10]:
    print(f"  [{p.get('kor_co_nm')}] '{p.get('spcl_cnd')}'")