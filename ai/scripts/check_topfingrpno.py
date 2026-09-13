"""FSS API의 topFinGrpNo(금융권역 코드) 후보들을 실제로 호출해서
신협이 어느 코드에 해당하는지 확인하는 스크립트 (수정판: 올바른 엔드포인트 사용)."""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import FSS_AUTH_KEY

import requests

BASE_URL = "https://finlife.fss.or.kr/finlifeapi/depositProductsSearch.json"

CANDIDATES = ["020000", "030200", "030300", "050000", "060000", "070000", "080000", "090000"]

print(f"FSS_AUTH_KEY 앞 5자리: {FSS_AUTH_KEY[:5] if FSS_AUTH_KEY else '(비어있음)'}")
print()

for code in CANDIDATES:
    params = {
        "auth": FSS_AUTH_KEY,
        "topFinGrpNo": code,
        "pageNo": 1,
    }
    res = requests.get(BASE_URL, params=params, timeout=10)

    print(f"--- topFinGrpNo={code} ---")
    print(f"  status_code: {res.status_code}")

    try:
        data = res.json()
        result = data.get("result", {})
        err_cd = result.get("err_cd")
        err_msg = result.get("err_msg")
        base_list = result.get("baseList", [])
        print(f"  err_cd: {err_cd} ({err_msg}), 상품 수: {len(base_list)}")
        if base_list:
            sample_names = sorted({p.get("kor_co_nm") for p in base_list[:30]})
            print(f"  기관명 샘플: {sample_names}")
            cu_matches = [n for n in sample_names if n and "신협" in n]
            if cu_matches:
                print(f"  *** '신협' 포함 기관명 발견: {cu_matches} ***")
    except Exception as e:
        print(f"  JSON 파싱 실패: {e}")
        print(f"  응답 앞부분: {res.text[:200]!r}")
    print()