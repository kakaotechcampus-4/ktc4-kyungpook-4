"""
finlife API - 페이지네이션까지 포함해서 전체 조합(은행/저축은행/신협 x 정기예금/적금)의
전체 데이터를 끝까지 받아서 tests/fixtures/*.json에 저장한다.

이전 스크립트(test_finlife_api.py)는 pageNo=1만 요청해서
total_count보다 적은 데이터만 저장했었음 - 이 스크립트가 그 문제를 고친 버전.

[저장 방식 - 원자적 저장 (PR #42 리뷰 반영)]
6개 타겟을 하나씩 받자마자 저장하면, 중간 타겟이 실패했을 때 앞 타겟은 이번 주 데이터,
뒤 타겟은 지난주 데이터로 섞인다. 그래서
  1단계: 6개를 전부 메모리에 받는다. 하나라도 실패하면 파일을 하나도 건드리지 않고 종료 코드 1.
  2단계: 6개를 각각 임시 파일(*.tmp)에 쓴다. 쓰다가 실패하면 임시 파일만 지우고 종료 코드 1.
  3단계: 6개를 원래 이름으로 바꾼다(os.replace). 이 단계는 순식간에 끝난다.
실패로 보는 경우: 요청 오류(네트워크·HTTP 오류), API 오류 코드(err_cd != 000),
0건 수집, API가 알려준 전체 건수(total_count)와 실제로 받은 건수가 다를 때.
"""
import json
import os
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
    ("은행 정기예금", DEPOSIT_URL, "020000", "deposit_sample.json"),
    ("은행 적금", SAVING_URL, "020000", "saving_sample.json"),
    ("저축은행 정기예금", DEPOSIT_URL, "030300", "deposit_savingsbank_sample.json"),
    ("저축은행 적금", SAVING_URL, "030300", "saving_savingsbank_sample.json"),
    ("신협 정기예금", DEPOSIT_URL, "032000", "deposit_cu_sample.json"),
    ("신협 적금", SAVING_URL, "032000", "saving_cu_sample.json"),
]


class FetchError(Exception):
    """API 가 오류 코드를 돌려줬거나 받은 데이터가 온전하지 않을 때."""


def _fail(label, reason):
    """하나라도 실패하면 파일을 하나도 바꾸지 않고 끝낸다(지난 수집본 6개 그대로 유지)."""
    print(f"[{label}] {reason} - 실패로 처리. 6개 파일 모두 기존 수집본을 유지합니다.")
    sys.exit(1)


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
        err_cd, err_msg = result.get("err_cd"), result.get("err_msg")
        if err_cd not in (None, "000"):
            # 오류 페이지를 건너뛰고 계속하면 일부 상품만 빠진 채 '성공'이 되므로 실패로 처리한다
            raise FetchError(f"API 오류 err_cd={err_cd} err_msg={err_msg} (페이지 {page_no})")

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
        sys.exit(1)

    # 1단계: 6개 전부 받기 - 이 단계에서는 파일을 하나도 건드리지 않는다
    collected = []  # (라벨, 저장 파일명, 데이터)
    for label, url, top_fin_grp_no, filename in TARGETS:
        print(f"[{label}] 수집 시작...")
        try:
            data = fetch_all_pages(url, top_fin_grp_no)
        except Exception as e:  # 네트워크·HTTP 오류, API 오류 코드, 응답 형식 이상
            _fail(label, f"수집 중 오류: {e}")
        result = data["result"]

        base_count = len(result["baseList"])
        option_count = len(result["optionList"])
        total_count = result.get("total_count")

        print(f"[{label}] total_count(API 보고)={total_count} / 실제 수집 baseList={base_count}, optionList={option_count}")

        if base_count == 0:
            _fail(label, "0건 수집")
        if total_count is not None and int(total_count) != base_count:
            _fail(label, f"건수 불일치 (API 보고 {total_count}건, 실제 {base_count}건)")

        collected.append((label, filename, data))
        print(f"[{label}] 수집 완료 (아직 저장 안 함)\n")
        time.sleep(0.5)

    # 2단계: 6개 모두 임시 파일에 쓰기 - 실패하면 임시 파일만 지우고 원본은 그대로 둔다
    written = []  # (임시 파일, 최종 파일, 라벨)
    try:
        for label, filename, data in collected:
            out_path = FIXTURES_DIR / filename
            tmp_path = FIXTURES_DIR / f"{filename}.tmp"
            tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            written.append((tmp_path, out_path, label))
    except OSError as e:
        for tmp_path, _, _ in written:
            tmp_path.unlink(missing_ok=True)
        print(f"임시 파일 저장 실패: {e} - 6개 파일 모두 기존 수집본을 유지합니다.")
        sys.exit(1)

    # 3단계: 6개를 한 번에 원래 이름으로 교체
    for tmp_path, out_path, label in written:
        os.replace(tmp_path, out_path)
        print(f"[{label}] 저장 완료: {out_path}")
    print(f"\n6개 모두 수집 성공 - 한 번에 저장 완료")


if __name__ == "__main__":
    main()