# -*- coding: utf-8 -*-
"""condition_type 카테고리를 새로 추가했을 때 쓰는 "전체 재추출" 프로세스를 한
스크립트로 묶은 것.

배경(PR #11 리뷰 답변용): 이 파이프라인은 캐시에 있는 결과를 규칙 기반으로
재분류하는 게 아니라, extract_conditions_ai.py --fresh로 원문(spcl_cnd/
prefCondMemo 등)부터 AI에게 전부 다시 보내서 새로 분류한다. SYSTEM_PROMPT의
카테고리 목록에 새 카테고리를 추가한 뒤 이 스크립트를 돌리면, 예전에 '기타'로
빠졌던 것 중 새 카테고리 조건에 맞는 게 자동으로 그쪽으로 재분류된다. 실제로
공제가입/연령조건을 추가할 때도 이 방식을 썼다.

이 스크립트가 하는 일 (기본 모드):
  1) 재추출 전(before) 분류 현황 스냅샷 - 캐시 파일에서 key별 "가장 오래된"
     행(=이전 프롬프트로 분류됐던 결과)을 기준으로 condition_type별 건수 집계
  2) extract_conditions_ai.py --fresh 실행 (전체 재추출, 새 결과는 캐시 파일
     뒤에 이어붙음)
  3) build_erd_tables.py 실행 (재추출된 캐시를 ERD 산출물에 반영)
  4) 재추출 후(after) 분류 현황 스냅샷 - key별 "가장 최근" 행(=지금 build가
     실제로 쓰는 결과) 기준으로 다시 집계하고, before와 비교해서 리포트 출력

주의(비용): --fresh는 대상 전체(현재 약 1,479건)를 매번 다시 호출한다. 캐시
파일은 지우지 않고 계속 이어붙이기만 해서, 새 카테고리를 추가할 때마다 파일이
계속 커진다(지금 이미 3,916줄/고유 1,479건 - 반복 실행 때문에 누적됨). 데이터가
더 늘어서 이 비용이 부담되면, "기타로 분류된 것만 추려서 그 후보만 재검토하는"
가벼운 스크립트를 별도로 만드는 걸 추천 - 이번 스코프에서는 백로그로 남겨둠.

사용법 (ai/ 폴더에서 실행):
  python scripts/reextract_for_new_category.py                # 전체 재추출 + 재빌드 + 리포트
  python scripts/reextract_for_new_category.py --limit 5       # 스모크 테스트(5건만)
  python scripts/reextract_for_new_category.py --report-only   # 재추출 없이 현재 캐시로 리포트만
"""
import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = AI_ROOT / "output" / "ai_condition_cache.jsonl"


def load_grouped_by_key():
    """key -> [파일에 등장한 순서대로의 모든 행] 딕셔너리로 캐시를 읽는다.
    (build_erd_tables.py처럼 '마지막 것만' 읽는 게 아니라, 재추출 전/후를
    비교하려고 전체 이력을 남긴다.)"""
    by_key = defaultdict(list)
    if not CACHE_PATH.exists():
        return by_key
    with CACHE_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            by_key[row["key"]].append(row)
    return by_key


def tally(by_key, which: str) -> Counter:
    """which='first' -> 각 key의 가장 오래된 분류, which='last' -> 가장 최근
    분류(=지금 build_erd_tables.py가 실제로 쓰는 것) 기준으로 condition_type
    카운트."""
    counter = Counter()
    for rows in by_key.values():
        row = rows[0] if which == "first" else rows[-1]
        for c in row.get("conditions") or []:
            counter[c.get("condition_type")] += 1
    return counter


def print_report(before: Counter, after: Counter, before_lines: int, before_keys: int):
    by_key_after = load_grouped_by_key()
    after_lines = sum(len(v) for v in by_key_after.values())
    after_keys = len(by_key_after)

    print()
    print("=== 재분류 리포트 (재추출 전 -> 재추출 후) ===")
    all_types = sorted(set(before) | set(after), key=lambda k: -(before.get(k, 0) + after.get(k, 0)))
    for t in all_types:
        b, a = before.get(t, 0), after.get(t, 0)
        diff = a - b
        sign = "+" if diff > 0 else ""
        print(f"  {t or '(없음)'}: {b} -> {a} ({sign}{diff})")
    print()
    print(f"캐시 파일 크기: {before_lines}줄/{before_keys}건(고유) -> {after_lines}줄/{after_keys}건(고유)")
    print("  (같은 key가 여러 번 등장하는 건 --fresh를 여러 번 돌린 이력 - 파일을 지우지")
    print("   않고 이어붙이는 구조라서 발생. 지금은 build_erd_tables.py가 마지막 행만")
    print("   읽어서 정확성엔 문제없지만, 계속 쌓이면 파일이 불필요하게 커진다.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="extract_conditions_ai.py에 그대로 전달(스모크 테스트용)")
    ap.add_argument("--report-only", action="store_true", help="재추출/재빌드 없이 현재 캐시 기준 리포트만 출력")
    args = ap.parse_args()

    by_key_before = load_grouped_by_key()
    before_counter = tally(by_key_before, "first")
    before_lines = sum(len(v) for v in by_key_before.values())
    before_keys = len(by_key_before)

    # 리포트 비교 기준(before)은 항상 "각 key의 가장 오래된 분류"로 고정한다.
    # report-only 모드에서는 "가장 최근 분류"를 after로 써서 지금까지 누적된
    # 전체 변화를 보여준다.
    if args.report_only:
        after_counter = tally(by_key_before, "last")
        print_report(before_counter, after_counter, before_lines, before_keys)
        return

    print("[1/2] extract_conditions_ai.py --fresh 실행 (전체 재추출)")
    cmd = [sys.executable, str(AI_ROOT / "scripts" / "extract_conditions_ai.py"), "--fresh"]
    if args.limit:
        cmd += ["--limit", str(args.limit)]
    subprocess.run(cmd, cwd=str(AI_ROOT), check=True)

    print("\n[2/2] build_erd_tables.py 실행 (재추출 결과를 ERD 산출물에 반영)")
    subprocess.run(
        [sys.executable, str(AI_ROOT / "scripts" / "build_erd_tables.py")],
        cwd=str(AI_ROOT),
        check=True,
    )

    after_by_key = load_grouped_by_key()
    after_counter = tally(after_by_key, "last")
    print_report(before_counter, after_counter, before_lines, before_keys)


if __name__ == "__main__":
    main()
