"""
group_id 재현성(reproducibility) 테스트.

배경: group_id 자체의 "이름"은 API 호출마다 달라져도 문제가 안 됨(계산 로직은
compute_extracted_total에서 group_id 문자열 값이 아니라 "같은 group_id를 가진
조건들"이라는 관계만 보고 최댓값을 취하기 때문 - build_erd_tables.py/
extract_conditions_ai.py 어디에도 group_id의 실제 문자열 값에 의존하는 코드가 없음).

문제가 될 수 있는 건 "이름"이 아니라 "묶음 구성(partition)" 그 자체 - 같은 원문
(spcl_cnd)을 여러 번 호출했을 때, 어떤 조건들끼리 같은 그룹으로 묶이는지(=서로
대체관계로 판단되는지)가 호출마다 달라지면, compute_extracted_total의 결과(그룹
안에서는 최댓값만, 그룹 밖은 합산)도 달라짐 - 이건 LLM 호출의 비결정성이라 프롬프트
로는 100% 막을 수 없고, "실제로 얼마나 흔들리는지"를 먼저 측정해야 함.

방법: group_id 판단이 특히 까다로운 대표 원문 몇 개(구간형/①②③번호형/구간+번호
혼합형)를 골라서 같은 원문을 N번 반복 호출하고, 매 호출마다 "조건 설명(description)
문자열을 key로 한 그룹 파티션"을 뽑아서 N번 사이에 얼마나 일치하는지 비교한다.
(group_id의 실제 문자열 값이 아니라 "이 두 조건이 같은 그�집에 속하는가/아닌가"라는
관계만 비교 - 그래야 이름이 바뀌는 건 무시하고 진짜 중요한 것만 봄)

주의: description 문자열 자체도 매 호출마다 표현이 살짝 달라질 수 있음(예: 조사나
어미가 바뀌는 정도). 이 스크립트는 "정확히 같은 문자열"로 매칭하므로, description이
달라지면 그 자체로 별도 이슈로 표시함(그룹 비교와는 분리해서 보고).

실행:
  python scripts\\test_group_id_stability.py               (기본 대표 케이스 5개, 각 5회)
  python scripts\\test_group_id_stability.py --repeats 10  (반복 횟수 조절)
  python scripts\\test_group_id_stability.py --from-cache --limit 5
      (output/ai_condition_cache.jsonl에서 group_id가 실제로 쓰인 원문을 골라 테스트.
       --from-cache 없으면 아래 SAMPLE_TEXTS의 대표 케이스만 사용)
"""
import argparse
import json
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import OPENAI_API_KEY, OPENAI_BASE_URL

from openai import OpenAI

# extract_conditions_ai.py에 이미 있는 call_ai()를 그대로 재사용 - 같은 프롬프트/파싱
# 로직으로 호출해야 실제 파이프라인과 동일한 조건에서 재현성을 측정할 수 있음.
sys.path.append(str(Path(__file__).resolve().parent))
from extract_conditions_ai import call_ai  # noqa: E402

CACHE_PATH = Path(__file__).resolve().parent.parent / "output" / "ai_condition_cache.jsonl"

# 대표 케이스: SYSTEM_PROMPT의 group_id 규칙이 실제로 갈리기 쉬운 3가지 패턴
# (①②③ 번호형 / 번호 없는 구간형 / 구간+독립조건 혼합형)을 하나씩 뽑음.
SAMPLE_TEXTS = [
    # 1) ①②③ 번호형 - 상한이 명시되고 그 안에서 하나만 인정되는 구조
    "최고 우대금리 0.5%p. ①급여이체 실적 보유 시 0.2%p ②당행 신용카드 실적 보유 시 "
    "0.2%p ③마케팅 정보 수신 동의 시 0.1%p",
    # 2) 번호 없는 구간형 - 신용점수 구간
    "신용점수 850점 이하~650점 초과 1.0%p, 650점 이하~350점 초과 2.0%p, "
    "350점 이하~1점 이상 3.0%p",
    # 3) 구간형(금액) - 번호 없이 나열
    "전월 카드 실적 300만원 이상 0.1%p, 500만원 이상 0.2%p, 1000만원 이상 0.3%p",
    # 4) 구간형 + 독립조건 혼합 - 그룹에 안 들어가야 하는 조건이 하나 섞여 있음
    "자동이체 실적 보유 시 0.1%p. 걸음수 100만보 이상 0.1%p, 200만보 이상 0.2%p, "
    "300만보 이상 0.3%p. 마케팅 정보 수신 동의 시 0.05%p",
    # 5) 대체관계가 아예 없는 경우(전부 독립) - "묶지 않아야 정상"인 케이스도 같이 봐야
    # "원래 안 묶이던 걸 잘못 묶는" 반대 방향 실수까지 잡을 수 있음
    "급여이체 실적 보유 시 0.2%p. 자동이체 실적 보유 시 0.1%p. 마케팅 정보 수신 동의 시 0.1%p.",
]


def load_cache_samples(limit):
    """캐시에서 group_id가 실제로 쓰인(=None이 아닌 값이 하나라도 있는) 원문 spcl_cnd를
    최대 limit개 골라온다. 캐시가 없거나 못 찾으면 빈 리스트."""
    if not CACHE_PATH.exists():
        print(f"[!] 캐시 파일이 없습니다: {CACHE_PATH} - --from-cache 없이 대표 케이스만 사용됨")
        return []
    picked = []
    seen_texts = set()
    with CACHE_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("error"):
                continue
            conds = row.get("conditions") or []
            if not any(c.get("group_id") for c in conds):
                continue
            text = row.get("spcl_cnd")
            if not text or text in seen_texts:
                continue
            seen_texts.add(text)
            picked.append(text)
            if len(picked) >= limit:
                break
    return picked


def partition_of(conditions):
    """conditions 리스트를 [group_id가 있는 것들은 그룹별로, 없는 것들은 각자 싱글턴]인
    frozenset의 집합으로 바꾼다. description 문자열을 조건의 식별자로 쓴다(같은 호출
    안에서 description이 중복되면 (설명, i번째)로 구분해서 잘못 합쳐지는 것을 방지)."""
    groups = {}
    for i, c in enumerate(conditions):
        ident = (c["description"], sum(1 for cc in conditions[:i] if cc["description"] == c["description"]))
        gid = c.get("group_id")
        key = ("GROUP", gid) if gid else ("SINGLE", ident)
        groups.setdefault(key, []).append(ident)
    return frozenset(frozenset(v) for v in groups.values())


def pair_relation(conditions):
    """설명 쌍(a, b)마다 "같은 그룹에 속하는가"(True/False)를 담은 dict.
    partition_of()와 달리 그룹 이름/구성 전체가 아니라 쌍 단위 관계라서, 조건 개수나
    순서가 호출마다 달라져도(설명이 살아있는 조건들끼리는) 비교가 가능함."""
    gid_of = {}
    for i, c in enumerate(conditions):
        ident = (c["description"], sum(1 for cc in conditions[:i] if cc["description"] == c["description"]))
        gid_of[ident] = c.get("group_id")
    idents = list(gid_of.keys())
    rel = {}
    for a, b in combinations(idents, 2):
        ga, gb = gid_of[a], gid_of[b]
        same = (ga is not None and ga == gb)
        rel[frozenset((a, b))] = same
    return rel


def run_case(client, text, repeats):
    print(f"\n{'=' * 70}\n원문: {text[:80]}{'...' if len(text) > 80 else ''}\n{'=' * 70}")
    all_conditions = []
    all_partitions = []
    all_relations = []
    for i in range(repeats):
        conditions, _, error = call_ai(client, text)
        if error:
            print(f"  [{i + 1}/{repeats}] 호출 실패: {error[:120]}")
            continue
        descs = [c["description"] for c in conditions]
        gids = [c.get("group_id") for c in conditions]
        print(f"  [{i + 1}/{repeats}] 조건 {len(conditions)}개, group_id: {gids}")
        all_conditions.append(conditions)
        all_partitions.append(partition_of(conditions))
        all_relations.append(pair_relation(conditions))

    if not all_conditions:
        print("  전부 실패 - 비교 불가")
        return {"text": text, "n_ok": 0, "n_partition_shapes": None, "flaky_pairs": []}

    # 1) 파티션(그룹 구성) 자체가 호출마다 몇 가지 형태로 나오는지
    shape_counts = Counter(all_partitions)
    print(f"  -> {len(all_conditions)}번 성공 중 서로 다른 그룹 구성: {len(shape_counts)}가지")
    if len(shape_counts) > 1:
        for shape, cnt in shape_counts.most_common():
            print(f"     {cnt}회: " + " | ".join(
                "{" + ", ".join(d for d, _ in sorted(g)) + "}" for g in shape
            ))

    # 2) 쌍 단위로, "매번 같은 그룹" vs "매번 다른 그룹"이 아니라 호출마다 왔다갔다 한
    # 쌍(=진짜 불안정한 쌍)만 뽑음. 설명이 매 호출에 다 등장하는 쌍만 비교 대상으로 삼음.
    pair_votes = {}
    for rel in all_relations:
        for pair, same in rel.items():
            pair_votes.setdefault(pair, []).append(same)
    flaky_pairs = [(pair, votes) for pair, votes in pair_votes.items()
                   if len(set(votes)) > 1 and len(votes) == len(all_conditions)]
    if flaky_pairs:
        print(f"  [!] 호출마다 판단이 바뀐 조건 쌍 {len(flaky_pairs)}개:")
        for pair, votes in flaky_pairs:
            (d1, _), (d2, _) = tuple(pair)
            print(f"      '{d1[:30]}' <-> '{d2[:30]}': {votes}")
    else:
        print("  -> 매번 등장한 조건 쌍들의 '같은 그룹 여부' 판단은 전부 일관됨")

    return {
        "text": text,
        "n_ok": len(all_conditions),
        "n_partition_shapes": len(shape_counts),
        "flaky_pairs": len(flaky_pairs),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=5, help="원문 하나당 반복 호출 횟수")
    ap.add_argument("--from-cache", action="store_true",
                     help="대표 케이스 대신 캐시에서 group_id가 쓰인 실제 원문을 가져와서 테스트")
    ap.add_argument("--limit", type=int, default=5, help="--from-cache일 때 가져올 원문 개수")
    args = ap.parse_args()

    if not OPENAI_API_KEY or not OPENAI_BASE_URL:
        print("[!] OPENAI_API_KEY / OPENAI_BASE_URL이 .env에 설정 안 돼 있음 - 진행 불가")
        return

    texts = load_cache_samples(args.limit) if args.from_cache else SAMPLE_TEXTS
    if not texts:
        print("테스트할 원문이 없습니다.")
        return

    client = OpenAI(api_key=OPENAI_API_KEY, base_url=f"{OPENAI_BASE_URL}/v1")
    results = [run_case(client, text, args.repeats) for text in texts]

    print(f"\n{'=' * 70}\n=== 요약 ===")
    unstable = [r for r in results if (r["n_partition_shapes"] or 0) > 1]
    print(f"테스트 원문 {len(results)}개 중 그룹 구성이 흔들린 원문: {len(unstable)}개")
    for r in unstable:
        print(f"  - '{r['text'][:50]}...' : {r['n_partition_shapes']}가지 구성, "
              f"불안정한 조건 쌍 {r['flaky_pairs']}개 (성공 {r['n_ok']}회)")
    if not unstable:
        print("  전부 안정적 - 최소 이번 대표 케이스들에서는 group_id 판단이 호출마다 흔들리지 않음")
        print("  (그렇다고 100% 결정론적이라는 보장은 아니고, 반복 횟수를 늘리거나")
        print("   --from-cache로 더 다양한 실제 원문을 넣어볼수록 신뢰도가 올라감)")


if __name__ == "__main__":
    main()
