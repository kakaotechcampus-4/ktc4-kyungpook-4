"""
주간 데이터 파이프라인 오케스트레이터.

실행 순서:
  1. 금감원 데이터 수집      (fetch_all_products.py)          ┐
  2. 신협 데이터 수집        (fetch_cu_rate_compare.py)       ├ 소스별 독립 실행 + 재시도
  3. 새마을금고 지점 목록    (fetch_kfcc_branches.py)         │ 실패해도 다음 소스 계속 진행
  4. 새마을금고 금리         (fetch_kfcc_rates.py --refresh)  │
  5. 새마을금고 중앙 조건    (fetch_kfcc_central_conditions.py)┘
  6. 판매 종료 감지          (fetch 성공 소스만 대상으로 missing_counts.json 갱신)
  7. AI 우대조건 추출        (extract_conditions_ai.py - 변경분만 자동 처리)
  8. ERD 산출물 빌드         (build_erd_tables.py)

사용법 (ai/ 폴더에서 실행):
  python scripts/run_pipeline.py                  # 전체 실행
  python scripts/run_pipeline.py --skip-fetch     # fetch 생략 (로컬 테스트)
  python scripts/run_pipeline.py --limit 10       # AI 추출 10건만 (스모크 테스트)
"""
import argparse
import json
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = AI_ROOT / "scripts"
FIXTURES = AI_ROOT / "tests" / "fixtures"
CACHE_PATH = AI_ROOT / "output" / "ai_condition_cache.jsonl"
MISSING_COUNTS_PATH = AI_ROOT / "output" / "missing_counts.json"
LOG_DIR = AI_ROOT / "output" / "pipeline_logs"

MISSING_THRESHOLD = 3
RETRY_COUNT = 3
RETRY_WAIT = 60  # 초

# extract_conditions_ai.py 의 FINLIFE_LIKE_SOURCES / EMPTY_SPCL_CND 와 동기화
_FINLIFE_SOURCES = [
    "deposit_sample.json",
    "saving_sample.json",
    "deposit_savingsbank_sample.json",
    "saving_savingsbank_sample.json",
]
_EMPTY_SPCL_CND = {"없음", "해당사항 없음", "해당없음", "우대금리 없음", ""}
_NONZERO_RATE_RE = re.compile(r"[1-9]\d*\.?\d*%p|0\.[1-9]\d*%p")


# ---------------------------------------------------------------------------
# 실행 유틸
# ---------------------------------------------------------------------------

def _run_with_retry(label: str, cmd: list[str]) -> bool:
    """소스 fetch 전용 실행기. 실패 시 재시도하고 최종 성공/실패를 bool로 반환.
    예외를 던지지 않으므로 한 소스 실패가 파이프라인 전체를 중단시키지 않는다."""
    for attempt in range(1, RETRY_COUNT + 1):
        print(f"\n[{label}] 시작 (시도 {attempt}/{RETRY_COUNT})")
        result = subprocess.run(cmd, cwd=str(AI_ROOT))
        if result.returncode == 0:
            print(f"[{label}] 완료")
            return True
        if attempt < RETRY_COUNT:
            print(f"[{label}] 실패 - {RETRY_WAIT}초 후 재시도...")
            time.sleep(RETRY_WAIT)
    print(f"[{label}] {RETRY_COUNT}회 재시도 후 최종 실패")
    return False


def _run(label: str, cmd: list[str]) -> None:
    """AI 추출·ERD 빌드 전용 실행기. 실패 시 파이프라인 중단."""
    print(f"\n[{label}] 시작")
    result = subprocess.run(cmd, cwd=str(AI_ROOT))
    if result.returncode != 0:
        raise RuntimeError(f"[{label}] 실패 (returncode={result.returncode})")
    print(f"[{label}] 완료")


# ---------------------------------------------------------------------------
# 소스 판별
# ---------------------------------------------------------------------------

def _key_to_source(key: str) -> str:
    """캐시 키에서 어느 소스(fetch 스크립트)의 상품인지 판별."""
    if key.startswith("cu_rate_compare.jsonl:"):
        return "신협"
    if key.startswith("kfcc_central:"):
        return "새마을금고"
    return "금감원"


# ---------------------------------------------------------------------------
# 판매 종료 감지
# ---------------------------------------------------------------------------

def _gather_current_keys() -> set[str]:
    """현재 fixture 파일에서 상품 키 집합 수집.
    extract_conditions_ai.py 의 gather_* 함수와 동일한 키 포맷을 사용해야
    캐시 키와 올바르게 비교된다."""
    keys: set[str] = set()

    for filename in _FINLIFE_SOURCES:
        path = FIXTURES / filename
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for base in (data.get("result", data).get("baseList") or []):
            spcl_cnd = (base.get("spcl_cnd") or "").strip()
            if spcl_cnd in _EMPTY_SPCL_CND:
                continue
            keys.add(f"{filename}:{base.get('fin_co_no')}:{base.get('fin_prdt_cd')}")

    cu_path = FIXTURES / "cu_rate_compare.jsonl"
    if cu_path.exists():
        seen: set = set()
        with cu_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                memo = (rec.get("prefCondMemo") or "").strip()
                if memo in _EMPTY_SPCL_CND or not _NONZERO_RATE_RE.search(memo):
                    continue
                dedup = (rec.get("cuIngno"), rec.get("stockCode"), rec.get("tretYn"))
                if dedup in seen:
                    continue
                seen.add(dedup)
                cu_ingno, stock_code, tret_yn = dedup
                keys.add(f"cu_rate_compare.jsonl:{cu_ingno}:{stock_code}_{tret_yn}")

    kfcc_path = FIXTURES / "kfcc_central_conditions_raw.jsonl"
    if kfcc_path.exists():
        with kfcc_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if (row.get("spcl_cnd_raw") or "").strip():
                    keys.add(f"kfcc_central:{row.get('goods_file', '')}")

    return keys


def _load_cache_keys() -> set[str]:
    """캐시에서 성공적으로 추출된 상품 키 목록 반환."""
    keys: set[str] = set()
    if not CACHE_PATH.exists():
        return keys
    with CACHE_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not row.get("error"):
                keys.add(row["key"])
    return keys


def _update_missing_and_detect(
    current_keys: set[str],
    cache_keys: set[str],
    successful_sources: set[str],
) -> list[str]:
    """누락 횟수를 갱신하고 MISSING_THRESHOLD 이상 누락된 상품 키 목록을 반환.

    - 이번 fetch에 있는 상품 → 누락 횟수 리셋
    - 이전에 있었는데 지금 없는 상품:
        → 해당 소스 fetch 성공 → 누락 횟수 +1 (실제로 사라진 것으로 판단)
        → 해당 소스 fetch 실패 → 누락 횟수 유지 (사이트 문제일 수 있으므로 판단 보류)
    - 누락 횟수 >= MISSING_THRESHOLD → 판매 종료로 판단
    """
    counts: dict = {}
    if MISSING_COUNTS_PATH.exists():
        counts = json.loads(MISSING_COUNTS_PATH.read_text(encoding="utf-8"))

    today = str(date.today())

    for key in current_keys:
        counts.pop(key, None)

    for key in cache_keys - current_keys:
        source = _key_to_source(key)
        if source not in successful_sources:
            continue  # 소스 fetch 실패 → 판매 종료 판단 보류
        entry = counts.get(key, {"count": 0, "first_missing": today})
        entry["count"] += 1
        entry["last_checked"] = today
        counts[key] = entry

    MISSING_COUNTS_PATH.write_text(
        json.dumps(counts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return [k for k, v in counts.items() if v["count"] >= MISSING_THRESHOLD]


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="주간 데이터 파이프라인")
    ap.add_argument("--skip-fetch", action="store_true", help="fetch 단계 생략 (로컬 테스트용)")
    ap.add_argument("--limit", type=int, help="AI 추출 건수 제한 (스모크 테스트용)")
    args = ap.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    py = sys.executable

    print("=== 파이프라인 시작 ===")

    fetch_results: dict[str, bool] = {"금감원": True, "신협": True, "새마을금고": True}

    if not args.skip_fetch:
        fetch_results["금감원"] = _run_with_retry(
            "1/5 금감원", [py, str(SCRIPTS / "fetch_all_products.py")]
        )
        fetch_results["신협"] = _run_with_retry(
            "2/5 신협", [py, str(SCRIPTS / "fetch_cu_rate_compare.py")]
        )

        branches_ok = _run_with_retry(
            "3/5 새마을금고 지점", [py, str(SCRIPTS / "fetch_kfcc_branches.py")]
        )
        if branches_ok:
            _run_with_retry(
                "4/5 새마을금고 금리",
                [py, str(SCRIPTS / "fetch_kfcc_rates.py"), "--refresh"],
            )
            central_ok = _run_with_retry(
                "5/5 새마을금고 중앙조건",
                [py, str(SCRIPTS / "fetch_kfcc_central_conditions.py")],
            )
            # 중앙조건이 AI 추출에 직접 사용되므로 성공 여부 기준
            fetch_results["새마을금고"] = central_ok
        else:
            print("[새마을금고] 지점 목록 수집 실패 - 금리/중앙조건 fetch 스킵")
            fetch_results["새마을금고"] = False

    failed_sources = [s for s, ok in fetch_results.items() if not ok]
    successful_sources = {s for s, ok in fetch_results.items() if ok}
    if failed_sources:
        print(f"\n⚠️  수집 실패 소스: {failed_sources} (이전 데이터 유지, missing count 판단 보류)")

    print("\n[변경 감지] 현재 상품 목록 ↔ 캐시 비교 중...")
    current_keys = _gather_current_keys()
    cache_keys = _load_cache_keys()
    new_count = len(current_keys - cache_keys)
    discontinued = _update_missing_and_detect(current_keys, cache_keys, successful_sources)
    missing_ongoing = len(
        [k for k in cache_keys - current_keys if _key_to_source(k) in successful_sources]
    )
    print(f"  신규: {new_count}건 / 누락 누적 중: {missing_ongoing}건 / 판매종료({MISSING_THRESHOLD}회 누락): {len(discontinued)}건")
    if discontinued:
        print(f"  판매종료 상품: {discontinued[:5]}{'...' if len(discontinued) > 5 else ''}")

    extract_cmd = [py, str(SCRIPTS / "extract_conditions_ai.py")]
    if args.limit:
        extract_cmd += ["--limit", str(args.limit)]
    _run("AI 추출 (변경분만)", extract_cmd)

    _run("ERD 빌드", [py, str(SCRIPTS / "build_erd_tables.py")])

    log_path = LOG_DIR / f"{date.today()}.log"
    log_path.write_text(
        f"SUCCESS\n"
        f"실행일: {date.today()}\n"
        f"수집 실패 소스: {failed_sources if failed_sources else '없음'}\n"
        f"신규: {new_count}건\n"
        f"판매종료: {len(discontinued)}건\n",
        encoding="utf-8",
    )
    print(f"\n=== 완료 (로그: {log_path}) ===")


if __name__ == "__main__":
    main()
