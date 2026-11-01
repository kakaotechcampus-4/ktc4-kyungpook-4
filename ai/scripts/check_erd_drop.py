"""
ERD 산출물 급감 검사 - "판단"만 한다. 커밋할지는 워크플로가 정한다.
(PR #42 리뷰: 판단은 건수를 가진 run_pipeline에서, 커밋 차단은 커밋 권한을 가진 워크플로에서)

[왜 필요한가]
2026-10-12(은행·저축은행 0건), 10-26(새마을금고 0건) 주간 실행에서 수집이 실패한 소스가
ERD에서 통째로 빠진 채 develop에 커밋됐고, develop push -> 자동 배포로 서비스 DB까지 들어갔다.
수집 스크립트의 종료 코드 처리(PR #41)로 대부분 막히지만, 그래도 빠져나가는 경우를 막는 마지막 관문이다.

[무엇과 무엇을 비교하나]
이번에 만든 ai/output/erd/*.jsonl  vs  git HEAD(=마지막으로 커밋된 develop 데이터)
  - git HEAD를 기준으로 쓰는 이유: 막혀서 커밋되지 않은 결과가 디스크에 남아 있어도,
    다음 실행은 항상 "마지막으로 정상 커밋된 데이터"와 비교한다.
  - 파일별 전체 행 수
  - 기관 유형(은행/저축은행/신협/새마을금고)별 기관 수·상품 수·옵션 수·조건 수
    전체 행 수만 보면 10/12처럼 은행·저축은행이 통째로 빠져도 상품 전체는 -2.8%뿐이라 못 잡는다.
    조건 수는 상품은 그대로인데 AI 추출만 실패한 경우를 잡기 위해 본다.
하나라도 DROP_LIMIT 이상 줄면 "급감". 이전 값이 0이거나 HEAD에 파일이 없으면 건너뛴다.

[기준값 20%의 근거 - 2026-09-23 ~ 10-28 ERD 커밋 기록]
  정상 실행에서 유형별로 줄어든 폭은 최대 1.4%(은행 조건 283 -> 279),
  사고 때는 해당 유형이 100% 사라졌다.

사용법:
  run_pipeline.py 9단계에서 자동으로 불린다.
  혼자 확인할 때 (ai/ 폴더에서): python scripts/check_erd_drop.py   (급감이면 종료 코드 1)
"""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
ERD_DIR = AI_ROOT / "output" / "erd"
FILES = ["institution", "product", "product_option", "product_condition"]
DROP_LIMIT = 0.2  # 20% 이상 줄면 급감
UNKNOWN = "알수없음"


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(AI_ROOT), capture_output=True)


def _read_now(name: str) -> list[dict]:
    """이번에 만든 파일. 파일이 없으면 빈 목록(=전부 빠진 것으로 본다)."""
    path = ERD_DIR / f"{name}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_head(name: str) -> list[dict] | None:
    """마지막 커밋본. HEAD에 파일이 없으면 None(비교 기준 없음)."""
    result = _git("show", f"HEAD:./output/erd/{name}.jsonl")
    if result.returncode != 0:
        return None
    text = result.stdout.decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _count_by_type(tables: dict[str, list[dict]]) -> dict[str, Counter]:
    """기관 유형별 기관·상품·옵션·조건 수.
    상품은 institution_code로, 옵션·조건은 product_id로 기관 유형을 찾는다."""
    inst_type = {r["institution_code"]: r.get("institution_type") or UNKNOWN for r in tables["institution"]}
    prod_type = {r["product_id"]: inst_type.get(r["institution_code"], UNKNOWN) for r in tables["product"]}
    return {
        "기관": Counter(inst_type.values()),
        "상품": Counter(prod_type.values()),
        "옵션": Counter(prod_type.get(r["product_id"], UNKNOWN) for r in tables["product_option"]),
        "조건": Counter(prod_type.get(r["product_id"], UNKNOWN) for r in tables["product_condition"]),
    }


def baseline_commit() -> str:
    """비교 기준(= 급감으로 막히면 그대로 남는 데이터)인 HEAD 커밋. 예: 'f7a068b (2026-10-29)'.
    Actions 는 최근 커밋 1개만 내려받으므로(shallow clone) 파일별 이력 대신 HEAD 를 쓴다."""
    result = _git("log", "-1", "--format=%h (%cs)")
    text = result.stdout.decode("utf-8").strip()
    return text or "알 수 없음"


def compare_with_head() -> tuple[list[tuple[str, int, int, str]], list[str]]:
    """반환: (항목별 [이름, 이전, 이번, 판정], 급감 항목 이름 목록)."""
    now = {name: _read_now(name) for name in FILES}
    head = {name: _read_head(name) for name in FILES}

    pairs = []  # (항목 이름, 이전 값, 이번 값)
    for name in FILES:
        if head[name] is not None:
            pairs.append((f"{name} 전체", len(head[name]), len(now[name])))
    if all(head[name] is not None for name in FILES):
        by_head = _count_by_type(head)
        by_now = _count_by_type(now)
        for kind in ("기관", "상품", "옵션", "조건"):
            for t in sorted(by_head[kind]):
                pairs.append((f"{t} {kind}", by_head[kind][t], by_now[kind].get(t, 0)))

    rows, failed = [], []
    for label, before, after in pairs:
        if before == 0:
            mark = "건너뜀(기준 없음)"
        elif (before - after) / before >= DROP_LIMIT:
            mark = "급감"
            failed.append(label)
        else:
            mark = "OK"
        rows.append((label, before, after, mark))
    return rows, failed


def render_report(rows: list[tuple[str, int, int, str]], failed: list[str], baseline: str) -> str:
    """사람이 읽는 결과표 (Actions 실행 요약 화면에 그대로 붙는다)."""
    lines = [
        "## 급감 검사 결과",
        "",
        f"- 비교 기준: 실행 시점의 마지막 커밋 `{baseline}` 의 ERD",
        f"- 기준: 항목 하나라도 {int(DROP_LIMIT * 100)}% 이상 줄면 급감",
        "",
        "| 항목 | 이전 | 이번 | 판정 |",
        "| --- | ---: | ---: | --- |",
    ]
    lines += [f"| {label} | {before:,} | {after:,} | {mark} |" for label, before, after, mark in rows]
    lines.append("")
    if failed:
        lines.append(f"**결과: 급감** - {', '.join(failed)}")
    else:
        lines.append("**결과: 통과**")
    return "\n".join(lines) + "\n"


def main() -> None:
    rows, failed = compare_with_head()
    print(render_report(rows, failed, baseline_commit()))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()