"""
build_erd_tables.py 산출물(institution/product/product_option/product_condition) 검수용.

체크 항목:
1. PK 중복(institution_code / product_id / option_id / condition_id)
2. FK 무결성(product.institution_code가 institution에 다 있는지,
   product_option.product_id / product_condition.product_id가 product에 다 있는지)
3. base_rate 이상치(없음/0/15% 초과)
4. period_months 없음 건수
5. institution_type / product_type / join_channel 별 건수 요약
6. product_condition rate_bonus 이상치(음수/10%p 초과) 및 condition_type 분포
7. 샘플 3건씩
"""
import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "output" / "erd"


def load_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def check_dupes(rows, key, label):
    counts = Counter(r[key] for r in rows)
    dupes = {k: c for k, c in counts.items() if c > 1}
    print(f"[{label}] {key} 중복: {len(dupes)}건" + (f" (예: {list(dupes.items())[:5]})" if dupes else ""))


def main():
    institutions = load_jsonl(OUT / "institution.jsonl")
    products = load_jsonl(OUT / "product.jsonl")
    options = load_jsonl(OUT / "product_option.jsonl")
    conditions = load_jsonl(OUT / "product_condition.jsonl")

    print(f"institution {len(institutions)}건 / product {len(products)}건 / "
          f"product_option {len(options)}건 / product_condition {len(conditions)}건\n")

    # 1) PK 중복
    check_dupes(institutions, "institution_code", "institution")
    check_dupes(products, "product_id", "product")
    check_dupes(options, "option_id", "product_option")
    if conditions:
        check_dupes(conditions, "condition_id", "product_condition")
    print()

    # 2) FK 무결성
    inst_codes = {r["institution_code"] for r in institutions}
    prod_ids = {r["product_id"] for r in products}
    bad_product_fk = [r["product_id"] for r in products if r["institution_code"] not in inst_codes]
    bad_option_fk = [r["option_id"] for r in options if r["product_id"] not in prod_ids]
    bad_condition_fk = [r["condition_id"] for r in conditions if r["product_id"] not in prod_ids]
    print(f"product -> institution FK 깨짐: {len(bad_product_fk)}건" + (f" (예: {bad_product_fk[:5]})" if bad_product_fk else ""))
    print(f"product_option -> product FK 깨짐: {len(bad_option_fk)}건" + (f" (예: {bad_option_fk[:5]})" if bad_option_fk else ""))
    if conditions:
        print(f"product_condition -> product FK 깨짐: {len(bad_condition_fk)}건" + (f" (예: {bad_condition_fk[:5]})" if bad_condition_fk else ""))
    print()

    # 3) base_rate 이상치
    no_rate = [o for o in options if o.get("base_rate") is None]
    zero_rate = [o for o in options if o.get("base_rate") == 0]
    high_rate = [o for o in options if (o.get("base_rate") or 0) > 15]
    print(f"base_rate 없음: {len(no_rate)}건")
    print(f"base_rate == 0: {len(zero_rate)}건 (예: {zero_rate[:3]})")
    print(f"base_rate > 15%: {len(high_rate)}건 (예: {high_rate[:5]})")
    print()

    # 4) period_months 없음
    no_term = [o for o in options if o.get("period_months") is None]
    print(f"period_months 없음: {len(no_term)}건 (예: {no_term[:3]})")
    print()

    # 5) 기관/상품 유형별 건수
    print("institution_type 별 건수:", Counter(r["institution_type"] for r in institutions))
    print("product_type 별 건수:", Counter(r["product_type"] for r in products))
    print("join_channel 별 건수:", Counter(r.get("join_channel") for r in products))
    print()

    # 6) product_condition 이상치 + 분포
    if conditions:
        no_bonus = [c for c in conditions if c.get("rate_bonus") is None]
        neg_bonus = [c for c in conditions if (c.get("rate_bonus") or 0) < 0]
        high_bonus = [c for c in conditions if (c.get("rate_bonus") or 0) > 10]
        print(f"[product_condition] rate_bonus 못 뽑음(원문만 보존): {len(no_bonus)}건")
        print(f"[product_condition] rate_bonus 음수: {len(neg_bonus)}건 (예: {neg_bonus[:3]})")
        print(f"[product_condition] rate_bonus > 10%p: {len(high_bonus)}건 (예: {high_bonus[:3]})")
        print("condition_type 별 건수:", Counter(c["condition_type"] for c in conditions))
        print()

    # 7) 샘플
    print("=== institution 샘플 3건 ===")
    for r in institutions[:3]:
        print(" ", r)
    print("=== product 샘플 3건 ===")
    for r in products[:3]:
        print(" ", r)
    print("=== product_option 샘플 3건 ===")
    for r in options[:3]:
        print(" ", r)
    if conditions:
        print("=== product_condition 샘플 3건 ===")
        for r in conditions[:3]:
            print(" ", r)


if __name__ == "__main__":
    main()
