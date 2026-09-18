"""신협 optionList에서 spcl_cnd='없음'인데도 intr_rate2 > intr_rate(우대폭 존재)인 경우가 있는지 확인."""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import FSS_AUTH_KEY

import requests

URL = "https://finlife.fss.or.kr/finlifeapi/depositProductsSearch.json"

base_list, option_list = [], []
page = 1
while True:
    params = {"auth": FSS_AUTH_KEY, "topFinGrpNo": "032000", "pageNo": page}
    res = requests.get(URL, params=params, timeout=10)
    result = res.json().get("result", {})
    base_list.extend(result.get("baseList", []))
    option_list.extend(result.get("optionList", []))
    max_page = result.get("max_page_no", 1)
    if page >= max_page or page > 15:
        break
    page += 1

print(f"base {len(base_list)}건, option {len(option_list)}건\n")

has_bonus = 0
no_bonus = 0
examples = []
for opt in option_list:
    intr_rate = opt.get("intr_rate")
    intr_rate2 = opt.get("intr_rate2")
    if intr_rate is None or intr_rate2 is None:
        continue
    bonus = round(intr_rate2 - intr_rate, 4)
    if bonus > 0.001:
        has_bonus += 1
        if len(examples) < 10:
            examples.append((opt.get("fin_co_no"), opt.get("fin_prdt_cd"), opt.get("save_trm"), intr_rate, intr_rate2, bonus))
    else:
        no_bonus += 1

print(f"우대폭 있음(intr_rate2 > intr_rate): {has_bonus}건")
print(f"우대폭 없음(intr_rate2 == intr_rate 또는 없음): {no_bonus}건\n")

if examples:
    print("우대폭 있는 예시 (최대 10개) - fin_co_no, fin_prdt_cd, save_trm, intr_rate, intr_rate2, bonus:")
    for ex in examples:
        print(f"  {ex}")