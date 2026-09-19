"""
신협(cu_rate_compare.jsonl) + 은행/저축은행(금감원 finlife: deposit_sample.json, saving_sample.json,
  deposit_savingsbank_sample.json, saving_savingsbank_sample.json)
원본 데이터를 BE ERD의 product / product_condition 테이블 형태로 변환.

[A안] product = 만기별 1행 flat 테이블 (institution + rate + period 내장).
  - institution.jsonl, product_option.jsonl 더 이상 생성하지 않음.
  - product_id = {PREFIX}-{기관코드}-{상품코드}-{만기개월} 형태로 만기 포함.
  - 우대조건(product_condition)은 만기별 product_id에 각각 연결(중복 저장).

실행 순서:
  1) python scripts\\extract_conditions_ai.py   (AI 호출 + 캐시 생성)
  2) python scripts\\build_erd_tables.py         (캐시 읽어서 최종 테이블 생성)

산출물: output/erd/product.jsonl, output/erd/product_condition.jsonl
"""
import json
import re
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
OUT = Path(__file__).resolve().parent.parent / "output" / "erd"
OUT.mkdir(parents=True, exist_ok=True)
AI_CACHE_PATH = Path(__file__).resolve().parent.parent / "output" / "ai_condition_cache.jsonl"

PCT_RE = re.compile(r"(\d+(?:\.\d+)?)")
TERM_RE = re.compile(r"(\d+)")


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


def is_freeform(name: str) -> bool:
    return "자유" in name


def fmt_date(s):
    """'20260819' -> '2026-08-19'. 이미 'YYYY-MM-DD' 형태면 그대로 반환."""
    if not s:
        return None
    s = str(s)
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s


def load_ai_cache():
    cache = {}
    if AI_CACHE_PATH.exists():
        with AI_CACHE_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    row = json.loads(line)
                    if not row.get("error"):
                        cache[row["key"]] = row
    return cache


# ---------------------------------------------------------------------------
# 공통 결과 저장소
# ---------------------------------------------------------------------------
products = {}            # product_id -> row dict
product_conditions = {}  # condition_id -> row dict
product_best_date = {}   # product_id -> 지금까지 본 것 중 가장 최신 snapshot_date
condition_count = {}     # product_id -> 해당 product에 달린 조건 수 (O(1) 카운터)
dup_stats = {"exact": 0, "conflict": 0, "conflict_examples": []}


def add_product(product_id, snapshot_date=None, **fields):
    """같은 product_id가 중복 등장하면:
    - base_rate/max_rate 동일 → exact dup(무시), snapshot_date만 최신으로 갱신
    - 값이 다름 → conflict: 더 최신 snapshot_date 쪽을 채택"""
    new_row = {
        "product_id": product_id,
        "offer_id": None,
        "source": "OFFICIAL",
        "snapshot_date": snapshot_date,
        **fields,
    }
    existing = products.get(product_id)
    if existing is None:
        products[product_id] = new_row
        product_best_date[product_id] = snapshot_date
        return
    if (existing.get("base_rate") == fields.get("base_rate")
            and existing.get("max_rate") == fields.get("max_rate")):
        dup_stats["exact"] += 1
        if snapshot_date and (product_best_date.get(product_id) is None
                              or snapshot_date > product_best_date[product_id]):
            products[product_id]["snapshot_date"] = snapshot_date
            product_best_date[product_id] = snapshot_date
        return
    dup_stats["conflict"] += 1
    if len(dup_stats["conflict_examples"]) < 10:
        dup_stats["conflict_examples"].append(
            (product_id, existing.get("base_rate"), fields.get("base_rate"))
        )
    best_date = product_best_date.get(product_id)
    if snapshot_date and best_date and snapshot_date <= best_date:
        return
    products[product_id] = new_row
    product_best_date[product_id] = snapshot_date


def add_product_condition(product_id, condition_type, rate_bonus, evidence_text,
                           source_url, exclusive_group=None,
                           verification_status=None, confidence_badge=None):
    idx = condition_count.get(product_id, 0) + 1
    condition_count[product_id] = idx
    condition_id = f"{product_id}-COND-{idx}"
    product_conditions[condition_id] = {
        "condition_id": condition_id,
        "product_id": product_id,
        "condition_type": condition_type,
        "rate_bonus": rate_bonus,
        "threshold_value": None,
        "exclusive_group": exclusive_group,
        "evidence_text": evidence_text,
        "source_url": source_url,
        "verification_status": verification_status,
        "confidence_badge": confidence_badge,
    }


def attach_ai_conditions(ai_cache, cache_key, product_id) -> int:
    """캐시에서 조건을 읽어 product_id(만기 포함)에 연결."""
    row = ai_cache.get(cache_key)
    if not row:
        return 0
    count = 0
    for cond in row["conditions"]:
        add_product_condition(
            product_id,
            condition_type=cond.get("condition_type") or "기타",
            rate_bonus=cond.get("bonus_rate"),
            evidence_text=cond["description"],
            source_url=row.get("evidence_url"),
            exclusive_group=cond.get("group_id"),
        )
        count += 1
    return count


# ---------------------------------------------------------------------------
# 1) 신협 cu_rate_compare.jsonl
# ---------------------------------------------------------------------------
CHANNEL_MAP = {"영업점": "대면", "스마트폰": "비대면", "인터넷": "비대면"}
CHANNEL_SUFFIX_RE = re.compile(r"\((대면|비대면)\)$")


def clean_product_name(stock_nm: str):
    """'정기예탁금(만기지급식)(대면)' -> ('정기예탁금(만기지급식)', '대면')"""
    m = CHANNEL_SUFFIX_RE.search(stock_nm)
    channel_label = m.group(1) if m else None
    name = CHANNEL_SUFFIX_RE.sub("", stock_nm).strip()
    return name, channel_label


def cu_product_type(product_type_tag: str, name: str) -> str:
    if product_type_tag == "deposit":
        return "예금"
    return "적금(자유적립식)" if is_freeform(name) else "적금(정액적립식)"


def process_cu(ai_cache=None):
    n_records = 0
    n_conditions = 0
    with (FIXTURES / "cu_rate_compare.jsonl").open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            n_records += 1

            cu_ingno = rec["cuIngno"]
            stock_code = rec["stockCode"]
            tret_yn = rec.get("tretYn")
            clean_name, channel_from_name = clean_product_name(rec["stockNm"])
            join_channel = CHANNEL_MAP.get(tret_yn, channel_from_name)
            period_months = parse_term_months(rec.get("monTy"))

            # stockCode가 대면/비대면 버전끼리 겹치므로 tretYn까지 포함
            product_id = f"CU-{cu_ingno}-{stock_code}-{tret_yn}-{period_months}"

            add_product(
                product_id,
                snapshot_date=rec.get("pubiBeginDate"),
                institution=rec["cuNm"],
                institution_type="신협",
                product_name=clean_name,
                product_type=cu_product_type(rec.get("_product_type"), clean_name),
                base_rate=parse_pct(rec.get("baseRate")),
                max_rate=parse_pct(rec.get("highRate")),
                period_months=period_months,
                amount_cap=rec.get("highLimtAmt"),
                region=None,
                join_channel=join_channel,
            )

            if ai_cache is not None:
                cache_key = f"cu:{cu_ingno}:{stock_code}:{tret_yn}"
                n_conditions += attach_ai_conditions(ai_cache, cache_key, product_id)

    return n_records, n_conditions


# ---------------------------------------------------------------------------
# 2) 새마을금고 kfcc_rates.jsonl (+ kfcc_branches.json 조인)
# ---------------------------------------------------------------------------
PAYMENT_SUFFIX_RE = re.compile(r"^(.*?)\s*기본이율$")


def payment_label(header: str):
    """'월지급식 기본이율' -> '월지급식', '기본이율' -> None"""
    m = PAYMENT_SUFFIX_RE.match(header.strip())
    if not m:
        return None
    label = m.group(1).strip()
    return label or None


def load_kfcc_branch_index():
    idx = {}
    data = json.loads((FIXTURES / "kfcc_branches.json").read_text(encoding="utf-8"))
    for b in data:
        key = (b["gmgoCd"], b["divNm"])
        idx[key] = b
    return idx


def kfcc_product_type(category: str, name: str) -> str:
    if category == "거치식예탁금":
        return "예금"
    return "적금(자유적립식)" if is_freeform(name) else "적금(정액적립식)"


def process_kfcc():
    branch_idx = load_kfcc_branch_index()
    n_records = 0
    missing_branch = []

    with (FIXTURES / "kfcc_rates.jsonl").open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            n_records += 1

            gmgo_cd = rec["gmgoCd"]
            gmgo_nm = rec["gmgoNm"]
            div_nm = rec["divNm"]
            r1, r2 = rec.get("r1"), rec.get("r2")

            branch = branch_idx.get((gmgo_cd, div_nm))
            if branch is None:
                div_cd = f"X{abs(hash(div_nm)) % 1000:03d}"
                missing_branch.append((gmgo_cd, div_nm))
            else:
                div_cd = branch["divCd"]

            inst_name = f"{gmgo_nm}새마을금고 {div_nm}"
            region = f"{r1} {r2}" if r1 and r2 else None
            join_channel = "비대면" if "더뱅킹" in gmgo_nm else "대면"

            for category in ("거치식예탁금", "적립식예탁금"):
                for entry in rec.get(category, []):
                    product_title = entry["product_title"]
                    headers = entry["headers"]
                    rate_headers = headers[2:]
                    rows = entry["rows"]

                    for col_idx, rate_header in enumerate(rate_headers):
                        suffix = payment_label(rate_header)
                        variant_name = f"{product_title}({suffix})" if suffix else product_title
                        join_ch = "비대면" if "더뱅킹" in product_title else join_channel

                        for row in rows:
                            if len(row) == len(headers):
                                term_raw, rates = row[1], row[2:]
                            elif len(row) == len(headers) - 1:
                                term_raw, rates = row[0], row[1:]
                            else:
                                continue
                            if col_idx >= len(rates):
                                continue
                            period_months = parse_term_months(term_raw)
                            base_rate = parse_pct(rates[col_idx])

                            product_id = f"KFCC-{gmgo_cd}-{div_cd}-{variant_name}-{period_months}"
                            add_product(
                                product_id,
                                snapshot_date=None,
                                institution=inst_name,
                                institution_type="새마을금고",
                                product_name=variant_name,
                                product_type=kfcc_product_type(category, variant_name),
                                base_rate=base_rate,
                                max_rate=base_rate,
                                period_months=period_months,
                                amount_cap=None,
                                region=region,
                                join_channel=join_ch,
                            )
    return n_records, missing_branch


# ---------------------------------------------------------------------------
# 3) 은행 / 저축은행 (금감원 finlife)
# ---------------------------------------------------------------------------
def classify_join_channel(join_way):
    if not join_way:
        return None
    has_branch = "영업점" in join_way
    has_online = any(k in join_way for k in ("인터넷", "스마트폰", "모바일", "앱"))
    if has_branch and has_online:
        return "대면+비대면"
    if has_branch:
        return "대면"
    if has_online:
        return "비대면"
    return join_way


def parse_amount(v):
    if v in (None, 0, "0"):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def process_finlife(filename: str, institution_type: str, product_type_tag: str,
                    parse_conditions: bool, ai_cache: dict):
    data = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
    result = data.get("result", data)
    base_list = result.get("baseList") or []
    option_list = result.get("optionList") or []

    options_by_product = {}
    for opt in option_list:
        key = (opt.get("fin_co_no"), opt.get("fin_prdt_cd"))
        options_by_product.setdefault(key, []).append(opt)

    inst_prefix = "BANK" if institution_type == "은행" else "SB"
    n_conditions = 0
    n_missing_options = 0

    for base in base_list:
        fin_co_no = base.get("fin_co_no")
        fin_prdt_cd = base.get("fin_prdt_cd")
        kor_co_nm = base.get("kor_co_nm")
        fin_prdt_nm = base.get("fin_prdt_nm")
        inst_code = f"{inst_prefix}-{fin_co_no}"

        opts = options_by_product.get((fin_co_no, fin_prdt_cd), [])
        if not opts:
            n_missing_options += 1

        # 적금: rsrv_type_nm별로 variant 분리 (예금은 None 하나뿐)
        variants = {}
        for opt in opts:
            variants.setdefault(opt.get("rsrv_type_nm"), []).append(opt)
        if not variants:
            variants = {None: []}
        multi_variant = len([k for k in variants if k]) > 1

        join_channel = classify_join_channel(base.get("join_way"))
        snapshot_date = fmt_date(base.get("dcls_strt_day"))
        amount_cap = parse_amount(base.get("max_limit"))
        cache_key = f"{filename}:{fin_co_no}:{fin_prdt_cd}"

        for rsrv_key, opt_rows in variants.items():
            if product_type_tag == "deposit":
                product_name = fin_prdt_nm
                p_type = "예금"
                id_suffix = ""
            else:
                if rsrv_key:
                    p_type = "적금(자유적립식)" if is_freeform(rsrv_key) else "적금(정액적립식)"
                    product_name = f"{fin_prdt_nm}({rsrv_key})" if multi_variant else fin_prdt_nm
                    id_suffix = f"-{rsrv_key}" if multi_variant else ""
                else:
                    p_type = "적금(정액적립식)"
                    product_name = fin_prdt_nm
                    id_suffix = ""

            # optionList 각 행(만기)마다 flat product 행 생성
            for opt in opt_rows:
                period_months = parse_term_months(opt.get("save_trm"))
                base_rate = opt.get("intr_rate")
                max_rate = opt.get("intr_rate2")
                if max_rate is None:
                    max_rate = base_rate

                product_id = f"{inst_code}-{fin_prdt_cd}{id_suffix}-{period_months}"
                add_product(
                    product_id,
                    snapshot_date=snapshot_date,
                    institution=kor_co_nm,
                    institution_type=institution_type,
                    product_name=product_name,
                    product_type=p_type,
                    base_rate=base_rate,
                    max_rate=max_rate,
                    period_months=period_months,
                    amount_cap=amount_cap,
                    region=None,
                    join_channel=join_channel,
                )

                if parse_conditions:
                    n_conditions += attach_ai_conditions(ai_cache, cache_key, product_id)

    return len(base_list), len(option_list), n_conditions, n_missing_options


FINLIFE_SOURCES = [
    ("deposit_sample.json", "은행", "deposit", True),
    ("saving_sample.json", "은행", "savings", True),
    ("deposit_savingsbank_sample.json", "저축은행", "deposit", True),
    ("saving_savingsbank_sample.json", "저축은행", "savings", True),
]


def main():
    ai_cache = load_ai_cache()
    if not ai_cache:
        print("[!] output/ai_condition_cache.jsonl이 없거나 비어있습니다.")
        print("    -> product_condition이 비어서 나올 수 있습니다. 먼저 이걸 실행하세요:")
        print("       python scripts\\extract_conditions_ai.py")
        print()

    n_cu, n_cu_conditions = process_cu(ai_cache)

    finlife_summary = []
    for filename, itype, ptag, parse_cond in FINLIFE_SOURCES:
        path = FIXTURES / filename
        if not path.exists():
            finlife_summary.append((filename, None))
            continue
        n_base, n_opt, n_cond, n_missing_opt = process_finlife(
            filename, itype, ptag, parse_cond, ai_cache
        )
        finlife_summary.append((filename, (n_base, n_opt, n_cond, n_missing_opt)))

    with (OUT / "product.jsonl").open("w", encoding="utf-8") as f:
        for row in products.values():
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (OUT / "product_condition.jsonl").open("w", encoding="utf-8") as f:
        for row in product_conditions.values():
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"신협 원본 레코드: {n_cu}건 (우대조건 추출 {n_cu_conditions}건)")
    print("은행/저축은행(finlife) 원본:")
    for filename, stats in finlife_summary:
        if stats is None:
            print(f"  {filename}: 파일 없음(스킵)")
            continue
        n_base, n_opt, n_cond, n_missing_opt = stats
        print(
            f"  {filename}: baseList {n_base}건 / optionList {n_opt}건"
            f" / 우대조건(AI) 추출 {n_cond}건"
            + (f" / 금리옵션 없는 상품 {n_missing_opt}건" if n_missing_opt else "")
        )
    print()
    print(f"product: {len(products)}건, product_condition: {len(product_conditions)}건")
    print(
        f"중복 product_id: 완전동일(무시) {dup_stats['exact']}건"
        f" / 값 충돌(최신 snapshot_date 채택) {dup_stats['conflict']}건"
    )
    if dup_stats["conflict_examples"]:
        print("충돌 예시(최대 10건):")
        for pid, old_rate, new_rate in dup_stats["conflict_examples"]:
            print(f"  {pid}: {old_rate} -> {new_rate}")


if __name__ == "__main__":
    main()
