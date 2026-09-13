"""서로 다른 기관인데 spcl_cnd가 완전히 똑같은 '템플릿 재사용 의심' 사례를 전수 조사."""
import json
from collections import defaultdict
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

FILES = [
    ("은행 정기예금", "deposit_sample.json"),
    ("은행 적금", "saving_sample.json"),
    ("저축은행 정기예금", "deposit_savingsbank_sample.json"),
    ("저축은행 적금", "saving_savingsbank_sample.json"),
    ("신협 정기예금", "deposit_cu_sample.json"),
    ("신협 적금", "saving_cu_sample.json"),
]


def analyze(label, filename):
    path = FIXTURES_DIR / filename
    if not path.exists():
        print(f"[{label}] 파일 없음: {path}\n")
        return

    data = json.loads(path.read_text(encoding="utf-8"))["result"]
    base_list = data["baseList"]

    # spcl_cnd -> set(kor_co_nm)
    text_to_orgs = defaultdict(set)
    text_to_count = defaultdict(int)
    for p in base_list:
        text = (p.get("spcl_cnd") or "").strip()
        if not text or text == "없음" or len(text) < 15:
            continue
        text_to_orgs[text].add(p.get("kor_co_nm"))
        text_to_count[text] += 1

    # 서로 다른 기관에서 반복된 텍스트만
    dup_groups = {t: orgs for t, orgs in text_to_orgs.items() if len(orgs) > 1}
    affected_products = sum(text_to_count[t] for t in dup_groups)
    total_candidates = sum(1 for p in base_list if (p.get("spcl_cnd") or "").strip() not in ("", "없음"))

    print(f"=== [{label}] ===")
    print(f"조건 있는 상품(전체): {total_candidates}건")
    print(f"템플릿 재사용 의심 그룹 수: {len(dup_groups)}개")
    print(f"영향받는 상품 수: {affected_products}건 ({affected_products/total_candidates*100:.1f}% of 조건있음)" if total_candidates else "")

    # 가장 많이 재사용된 순으로 상위 3개 템플릿만 예시로
    top = sorted(dup_groups.items(), key=lambda x: len(x[1]), reverse=True)[:3]
    for text, orgs in top:
        print(f"  - {len(orgs)}개 기관, {text_to_count[text]}개 상품 공유: {text[:60]}...")
        print(f"    기관 예시: {sorted(orgs)[:5]}")
    print()


def main():
    for label, filename in FILES:
        analyze(label, filename)


if __name__ == "__main__":
    main()