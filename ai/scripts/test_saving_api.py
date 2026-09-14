"""
금융감독원 '금융상품 한눈에' 적금 API 테스트 스크립트.
정기예금(test_finlife_api.py)과 별도 엔드포인트라 따로 호출한다.
"""
import json
import sys
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import FSS_AUTH_KEY

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://finlife.fss.or.kr/finlifeapi/savingProductsSearch.json"
TOP_FIN_GRP_NO = "020000"  # 020000=은행, 030300=저축은행


def main():
    if not FSS_AUTH_KEY:
        print("FSS_AUTH_KEY가 없습니다. .env를 확인하세요.")
        return

    params = {
        "auth": FSS_AUTH_KEY,
        "topFinGrpNo": TOP_FIN_GRP_NO,
        "pageNo": "1",
    }

    res = requests.get(BASE_URL, params=params, timeout=30)
    res.raise_for_status()
    data = res.json()

    result = data.get("result", {})
    print("err_cd:", result.get("err_cd"), "/ err_msg:", result.get("err_msg"))
    print("total_count:", result.get("total_count"))

    base_list = result.get("baseList", [])
    option_list = result.get("optionList", [])
    if base_list:
        print("\n첫 번째 적금 상품 샘플:")
        print(json.dumps(base_list[0], ensure_ascii=False, indent=2))
    if option_list:
        print("\n첫 번째 옵션 샘플 (rsrv_type 필드 확인용):")
        print(json.dumps(option_list[0], ensure_ascii=False, indent=2))

    out_path = FIXTURES_DIR / "saving_sample.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n전체 응답을 저장했습니다: {out_path}")


if __name__ == "__main__":
    main()