"""
base_rate == 0%가 새마을금고(kfcc_rates.jsonl) / 은행·저축은행(finlife) 쪽에서
얼마나, 왜 나오는지 진단. (신협 cu_rate_compare.jsonl 쪽은 이미 확인함 - 3건뿐이고
정상적인 원본 데이터였음)
"""
import json
import re
from collections import Counter
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

PCT_RE = re.compile(r"(\d+(?:\.\d+)?)")
TERM_RE = re.compile(r"(\d+)")
PAYMENT_SUFFIX_RE = re.compile(r"^(.*?)\s*기본이율$")


def parse_pct(s):
    if s is None:
        return None
    m = PCT_RE.search(str(s))
    return float(m.group(1)) if m else None


def parse_term_months(s):
    if s is None:
        return None
    m = TERM_RE.search(str(s))
    return int(m.group(1)) if m else None


def payment_label(header):
    m = PAYMENT_SUFFIX_RE.match(header.strip())
    if not m:
        return None
    label = m.group(1).strip()
    return label or None


# ---------------------------------------------------------------------------
# 1) 새마을금고 kfcc_rates.jsonl 진단
# ---------------------------------------------------------------------------
kfcc_zero_by_category = Counter()
kfcc_zero_by_term = Counter()
kfcc_total_by_term = Counter()
kfcc_zero_by_branch = Counter()
kfcc_raw_samples = []

path = FIXTURES / "kfcc_rates.jsonl"
if path.exists():
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            gmgo_cd = rec.get("gmgoCd")
            gmgo_nm = rec.get("gmgoNm")
            div_nm = rec.get("divNm")

            for category in ("거치식예탁금", "적립식예탁금"):
                for entry in rec.get(category, []):
                    headers = entry.get("headers", [])
                    rate_headers = headers[2:]
                    rows = entry.get("rows", [])
                    product_title = entry.get("product_title")

                    for col_idx, rate_header in enumerate(rate_headers):
                        for row in rows:
                            if len(row) == len(headers):
                                term_raw = row[1]
                                rates = row[2:]
                            elif len(row) == len(headers) - 1:
                                term_raw = row[0]
                                rates = row[1:]
                            else:
                                continue
                            if col_idx >= len(rates):
                                continue
                            term_months = parse_term_months(term_raw)
                            rate = parse_pct(rates[col_idx])
                            kfcc_total_by_term[term_months] += 1
                            if rate == 0.0:
                                kfcc_zero_by_category[category] += 1
                                kfcc_zero_by_term[term_months] += 1
                                kfcc_zero_by_branch[(gmgo_cd, div_nm)] += 1
                                if len(kfcc_raw_samples) < 8:
                                    kfcc_raw_samples.append({
                                        "gmgoNm": gmgo_nm, "divNm": div_nm,
                                        "category": category, "product_title": product_title,
                                        "rate_header": rate_header, "term_raw": term_raw,
                                        "raw_rate_value": rates[col_idx], "row": row,
                                    })

    print("=== [KFCC] 전체 레코드 term(개월)별 분포 ===")
    for k, v in sorted(kfcc_total_by_term.items(), key=lambda x: (x[0] is None, x[0])):
        print(f"  {k}개월: {v}건")
    print()
    print("=== [KFCC] base_rate==0 인 케이스의 category(거치식/적립식)별 분포 ===")
    for k, v in kfcc_zero_by_category.most_common():
        print(f"  {k}: {v}건")
    print()
    print("=== [KFCC] base_rate==0 인 케이스의 term(개월)별 분포 ===")
    for k, v in sorted(kfcc_zero_by_term.items(), key=lambda x: (x[0] is None, x[0])):
        print(f"  {k}개월: {v}건 (전체 {kfcc_total_by_term[k]}건 중)")
    print()
    print(f"=== [KFCC] base_rate==0 이 발생한 서로 다른 지점 개수: {len(kfcc_zero_by_branch)}개 ===")
    print("상위 5개 지점:", kfcc_zero_by_branch.most_common(5))
    print()
    print("=== [KFCC] 원본 샘플 8건 ===")
    for s in kfcc_raw_samples:
        print(" ", json.dumps(s, ensure_ascii=False))
else:
    print("kfcc_rates.jsonl 파일을 못 찾음")

print()
print("=" * 70)
print()

# ---------------------------------------------------------------------------
# 2) 은행/저축은행 finlife 파일 진단
# ---------------------------------------------------------------------------
FINLIFE_FILES = [
    "deposit_sample.json", "saving_sample.json",
    "deposit_savingsbank_sample.json", "saving_savingsbank_sample.json",
]

for filename in FINLIFE_FILES:
    fpath = FIXTURES / filename
    if not fpath.exists():
        print(f"[{filename}] 파일 없음 - 스킵")
        continue
    data = json.loads(fpath.read_text(encoding="utf-8"))
    result = data.get("result", data)
    base_list = result.get("baseList") or []
    option_list = result.get("optionList") or []
    base_by_key = {(b.get("fin_co_no"), b.get("fin_prdt_cd")): b for b in base_list}

    zero_opts = [o for o in option_list if o.get("intr_rate") == 0]
    print(f"[{filename}] optionList {len(option_list)}건 중 intr_rate==0: {len(zero_opts)}건")
    for o in zero_opts[:5]:
        base = base_by_key.get((o.get("fin_co_no"), o.get("fin_prdt_cd")), {})
        print("   ", {
            "기관": base.get("kor_co_nm"), "상품명": base.get("fin_prdt_nm"),
            "save_trm": o.get("save_trm"), "rsrv_type_nm": o.get("rsrv_type_nm"),
            "intr_rate": o.get("intr_rate"), "intr_rate2": o.get("intr_rate2"),
        })