"""
finlife API - 페이지네이션까지 포함해서 4개 조합(은행/저축은행 x 정기예금/적금)
전체 데이터를 끝까지 받아와 tests/fixtures/*.json에 덮어쓴다.

이전 스크립트들(test_finlife_api.py 등)은 pageNo=1만 요청해서
total_count보다 적은 데이터만 저장했었음 - 이 스크립트가 그 문제를 고친 버전.
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

DEPOSIT_URL = "https://finlife.fss.or.kr/finlifeapi/depositProductsSearch.json"
SAVING_URL = "https://finlife.fss.or.kr/finlifeapi/savingProductsSearch.json"

# (라벨, URL, topFinGrpNo, 저장 파일명)
TARGETS = [
    ("은행/정기예금", DEPOSIT_URL, "020000", "deposit_sample.json"),
    ("은행/적금", SAVING_URL, "020000", "saving_sample.json"),
    ("저축은행/정기예금", DEPOSIT_URL, "030300", "deposit_savingsbank_sample.json"),
    ("저축은행/적금", SAVING_URL, "030300", "saving_savingsbank_sample.json"),
]


def fetch_all_pages(url, top_fin_grp_no):
    """pageNo=1부터 max_page_no까지 전부 호출해서 baseList/optionList를 합친다."""
    all_base, all_option = [], []
    page_no = 1
    max_page_no = 1  # 첫 응답 받기 전 임시값
    merged_result = None

    while page_no <= max_page_no:
        params = {
            "auth": FSS_AUTH_KEY,
            "topFinGrpNo": top_fin_grp_no,
            "pageNo": str(page_no),
        }
        res = requests.get(url, params=params, timeout=30)
        res.raise_for_status()
        data = res.json()
        result = data["result"]

        if merged_result is None:
            merged_result = result

        max_page_no = int(result.get("max_page_no", 1))
        all_base.extend(result.get("baseList", []))
        all_option.extend(result.get("optionList", []))

        print(f"    페이지 {page_no}/{max_page_no} 완료 (누적 baseList {len(all_base)}건)")

        page_no += 1
        if page_no <= max_page_no:
            time.sleep(0.5)

    merged_result["baseList"] = all_base
    merged_result["optionList"] = all_option
    return {"result": merged_result}


def main():
    if not FSS_AUTH_KEY:
        print("FSS_AUTH_KEY가 없습니다. .env를 확인하세요.")
        return

    for label, url, top_fin_grp_no, filename in TARGETS:
        print(f"[{label}] 수집 시작...")
        data = fetch_all_pages(url, top_fin_grp_no)
        result = data["result"]

        base_count = len(result["baseList"])
        option_count = len(result["optionList"])
        total_count = result.get("total_count")

        print(f"[{label}] total_count(API 보고)={total_count} / 실제 수집 baseList={base_count}, optionList={option_count}")

        out_path = FIXTURES_DIR / filename
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{label}] 저장 완료: {out_path}\n")

        time.sleep(0.5)


if __name__ == "__main__":
    main()