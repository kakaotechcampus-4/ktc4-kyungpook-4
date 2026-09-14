"""
신협(cu_rate_compare.jsonl) + 새마을금고(kfcc_rates.jsonl, kfcc_branches.json)
+ 은행/저축은행(금감원 finlife: deposit_sample.json, saving_sample.json,
deposit_savingsbank_sample.json, saving_savingsbank_sample.json)
원본 데이터를 BE ERD의 institution / product / product_option / product_condition
테이블 형태로 변환.

가정(확인 안 된 부분, BE와 맞춰야 함):
- institution_type: "신협", "새마을금고", "은행", "저축은행" (한글 그대로)
- source: "OFFICIAL" (기관 공식 전자공시 출처)
- product.run_id: 이 스크립트에서는 채우지 않음(null) - batch_run 레코드는
  BE 임포트 단계에서 생성/연결한다고 가정
- product_condition(우대조건): 은행(finlife) 데이터의 spcl_cnd 텍스트만 이번에
  파싱해서 채움. 신협/새마을금고(원문이 비정형 텍스트/"없음"으로만 있음)와
  저축은행(이번 라운드에서는 범위 제외하기로 함)은 채우지 않음.
  파싱은 "가./나./1./-" 같은 마커로 문장을 나눈 뒤, 문장 안의 "숫자%p" 패턴을
  가산금리로 추출하는 best-effort 방식 - 완벽하지 않을 수 있어 evidence_text에
  원문을 그대로 같이 남겨서 나중에 검토 가능하게 함.

산출물: out/institution.jsonl, out/product.jsonl, out/product_option.jsonl,
out/product_condition.jsonl
"""
import json
import re
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
OUT = Path(__file__).resolve().parent.parent / "output" / "erd"
OUT.mkdir(parents=True, exist_ok=True)

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


def rate_type_of(name: str) -> str:
    return "복리" if "복리" in name else "단리"


# ---------------------------------------------------------------------------
# 공통 결과 저장소 (institution_code 기준 중복 제거)
# ---------------------------------------------------------------------------
institutions = {}      # institution_code -> row dict
products = {}           # product_id -> row dict
product_options = {}    # option_id -> row dict (중복 방지)
product_conditions = {} # condition_id -> row dict
option_best_date = {}   # option_id -> 이 값을 채택할 때 근거로 쓴 snapshot_date
product_best_date = {}  # product_id -> 지금까지 본 것 중 가장 최신 snapshot_date
dup_stats = {"exact": 0, "conflict": 0, "conflict_examples": []}


def add_institution(code, name, itype, region, is_active=True):
    if code not in institutions:
        institutions[code] = {
            "institution_code": code,
            "name": name,
            "institution_type": itype,
            "region": region,
            "is_active": is_active,
        }


def add_product(product_id, snapshot_date=None, **fields):
    # 같은 product_id가 여러 term 레코드에서 반복 등장하므로 대부분 필드는 처음 값만 채택.
    # snapshot_date만은 지금까지 본 것 중 가장 최신 날짜로 계속 갱신한다(원본 파일에
    # 서로 다른 수집일 데이터가 섞여 들어와 있는 경우가 실제로 있어서).
    if product_id not in products:
        row = {"product_id": product_id, "offer_id": None, "run_id": None, "source": "OFFICIAL",
               "snapshot_date": snapshot_date}
        row.update(fields)
        products[product_id] = row
        product_best_date[product_id] = snapshot_date
    elif snapshot_date and (product_best_date.get(product_id) is None or snapshot_date > product_best_date[product_id]):
        products[product_id]["snapshot_date"] = snapshot_date
        product_best_date[product_id] = snapshot_date


def add_product_option(product_id, period_months, rate_type, reserve_type, base_rate, max_rate, snapshot_date=None):
    option_id = f"{product_id}-{period_months}-{rate_type}"
    new_row = {
        "option_id": option_id,
        "product_id": product_id,
        "period_months": period_months,
        "rate_type": rate_type,
        "reserve_type": reserve_type,
        "base_rate": base_rate,
        "max_rate": max_rate,
    }
    existing = product_options.get(option_id)
    if existing is None:
        product_options[option_id] = new_row
        option_best_date[option_id] = snapshot_date
        return
    if existing["base_rate"] == base_rate and existing["max_rate"] == max_rate:
        dup_stats["exact"] += 1
        return
    # 값이 다른 경우: 원본에 서로 다른 수집일 데이터가 섞여 있을 수 있으므로
    # snapshot_date가 더 최신인 쪽을 채택한다(둘 다 날짜가 없거나 같으면 나중 값으로 덮어씀).
    dup_stats["conflict"] += 1
    if len(dup_stats["conflict_examples"]) < 10:
        dup_stats["conflict_examples"].append((option_id, existing, new_row))
    best_date = option_best_date.get(option_id)
    if snapshot_date and best_date and snapshot_date <= best_date:
        return  # 기존 값이 더 최신이거나 같음 -> 기존 값 유지
    product_options[option_id] = new_row
    option_best_date[option_id] = snapshot_date


def add_product_condition(product_id, condition_type, rate_bonus, evidence_text,
                           evidence_url, verification_status, confidence_badge):
    idx = sum(1 for c in product_conditions.values() if c["product_id"] == product_id) + 1
    condition_id = f"{product_id}-COND-{idx}"
    product_conditions[condition_id] = {
        "condition_id": condition_id,
        "product_id": product_id,
        "condition_type": condition_type,
        "rate_bonus": rate_bonus,
        "threshold_value": None,
        "threshold_unit": None,
        "apply_period_min": None,
        "apply_period_max": None,
        "exclusion_group": None,
        "evidence_text": evidence_text,
        "evidence_url": evidence_url,
        "verification_status": verification_status,
        "confidence_badge": confidence_badge,
    }


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


def process_cu():
    n_records = 0
    with (FIXTURES / "cu_rate_compare.jsonl").open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            n_records += 1

            cu_code = f"CU-{rec['cuIngno']}"
            add_institution(cu_code, rec["cuNm"], "신협", None)

            clean_name, channel_from_name = clean_product_name(rec["stockNm"])
            join_channel = CHANNEL_MAP.get(rec.get("tretYn"), channel_from_name)

            # 주의: stockCode가 대면/비대면 버전끼리 겹치는 경우가 실제로 있어서
            # (예: 정기적금(대면)/정기적금(비대면)이 둘 다 stockCode=1701),
            # tretYn(채널)까지 id에 포함시켜야 서로 다른 상품이 덮어써지지 않는다.
            product_id = f"{cu_code}-{rec['stockCode']}-{rec.get('tretYn')}"
            join_limt = rec.get("joinLimtCode")
            membership_required = None if join_limt is None else (join_limt != "제한없음")

            terms_parts = [rec.get("dueAfIntRateMemo"), rec.get("etcAtntMatt")]
            terms_text = "\n\n".join(p for p in terms_parts if p) or None

            snapshot_date = rec.get("pubiBeginDate")
            add_product(
                product_id,
                institution_code=cu_code,
                product_name=clean_name,
                product_type=cu_product_type(rec.get("_product_type"), clean_name),
                amount_min=None,
                amount_cap=rec.get("highLimtAmt"),
                monthly_min=None,
                monthly_cap=None,
                terms_text=terms_text,
                region=None,
                join_channel=join_channel,
                membership_required=membership_required,
                new_customer_only=None,
                min_age=None,
                max_age=None,
                parse_status="PARSED",
                snapshot_date=snapshot_date,
                sale_end_date=None,
                is_active=True,
            )

            period_months = parse_term_months(rec.get("monTy"))
            add_product_option(
                product_id,
                period_months=period_months,
                rate_type=rate_type_of(clean_name),
                reserve_type="거치식" if rec.get("_product_type") == "deposit" else (
                    "자유적립식" if is_freeform(clean_name) else "정액적립식"
                ),
                base_rate=parse_pct(rec.get("baseRate")),
                max_rate=parse_pct(rec.get("highRate")),
                snapshot_date=snapshot_date,
            )
    return n_records


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
                div_cd = f"X{abs(hash(div_nm)) % 1000:03d}"  # 폴백(비상용), review 필요
                missing_branch.append((gmgo_cd, div_nm))
            else:
                div_cd = branch["divCd"]

            inst_code = f"KFCC-{gmgo_cd}-{div_cd}"
            inst_name = f"{gmgo_nm}새마을금고 {div_nm}"
            region = f"{r1} {r2}" if r1 and r2 else None
            add_institution(inst_code, inst_name, "새마을금고", region)

            for category in ("거치식예탁금", "적립식예탁금"):
                for entry in rec.get(category, []):
                    product_title = entry["product_title"]
                    headers = entry["headers"]
                    rate_headers = headers[2:]
                    rows = entry["rows"]

                    # 헤더 열마다(월지급식/만기지급식 등) 별도 상품으로 취급
                    for col_idx, rate_header in enumerate(rate_headers):
                        suffix = payment_label(rate_header)
                        variant_name = f"{product_title}({suffix})" if suffix else product_title
                        product_id = f"KFCC-{gmgo_cd}-{div_cd}-{variant_name}"

                        join_channel = "비대면" if "더뱅킹" in product_title else "대면"
                        add_product(
                            product_id,
                            institution_code=inst_code,
                            product_name=variant_name,
                            product_type=kfcc_product_type(category, variant_name),
                            amount_min=None,
                            amount_cap=None,
                            monthly_min=None,
                            monthly_cap=None,
                            terms_text=None,
                            region=region,
                            join_channel=join_channel,
                            membership_required=None,
                            new_customer_only=None,
                            min_age=None,
                            max_age=None,
                            parse_status="PARSED",
                            snapshot_date=None,
                            sale_end_date=None,
                            is_active=True,
                        )

                        for row in rows:
                            if len(row) == len(headers):
                                term_raw = row[1]
                                rates = row[2:]
                            elif len(row) == len(headers) - 1:
                                term_raw = row[0]
                                rates = row[1:]
                            else:
                                continue  # 예상 밖 모양 - 스킵(로그로 남겨도 됨)

                            if col_idx >= len(rates):
                                continue
                            period_months = parse_term_months(term_raw)
                            base_rate = parse_pct(rates[col_idx])
                            add_product_option(
                                product_id,
                                period_months=period_months,
                                rate_type=rate_type_of(variant_name),
                                reserve_type=(
                                    "거치식" if category == "거치식예탁금" else (
                                        "자유적립식" if is_freeform(variant_name) else "정액적립식"
                                    )
                                ),
                                base_rate=base_rate,
                                max_rate=base_rate,  # 새마을금고 데이터엔 우대 포함 최고금리 구분이 없음
                            )
    return n_records, missing_branch


# ---------------------------------------------------------------------------
# 3) 은행 / 저축은행 (금감원 finlife: deposit_*.json, saving_*.json)
# ---------------------------------------------------------------------------
CONDITION_SPLIT_RE = re.compile(r"(?:^|\n)\s*(?:[①-⑩]|[가-하]\.|\d+[.)]|[-*※□○·]+)\s*")
BONUS_RATE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*p?")
CONDITION_KEYWORDS = [
    ("급여이체", "급여이체"),
    ("자동이체", "자동이체"),
    ("첫거래", "신규고객"),
    ("신규", "신규고객"),
    ("카드", "카드실적"),
    ("마케팅", "마케팅동의"),
    ("공과금", "공과금이체"),
    ("연금", "연금수령"),
    ("비대면", "비대면가입"),
    ("모바일", "비대면가입"),
    ("인터넷", "비대면가입"),
    ("앱", "비대면가입"),
]
EMPTY_SPCL_CND = {"없음", "해당사항 없음", "해당없음", "우대금리 없음", ""}
FINLIFE_SOURCE_URL = "https://finlife.fss.or.kr"


def classify_condition_type(text: str) -> str:
    for kw, label in CONDITION_KEYWORDS:
        if kw in text:
            return label
    return "기타"


def split_conditions(text: str):
    if not text:
        return []
    text = text.strip()
    if text in EMPTY_SPCL_CND:
        return []
    parts = [p.strip() for p in CONDITION_SPLIT_RE.split(text) if p and p.strip()]
    if not parts:
        parts = [text]
    return parts


def extract_conditions(product_id: str, spcl_cnd: str) -> int:
    count = 0
    for line in split_conditions(spcl_cnd):
        m = BONUS_RATE_RE.search(line)
        rate_bonus = float(m.group(1)) if m else None
        add_product_condition(
            product_id,
            condition_type=classify_condition_type(line),
            rate_bonus=rate_bonus,
            evidence_text=line,
            evidence_url=FINLIFE_SOURCE_URL,
            verification_status="공식(금감원 공시)",
            confidence_badge="공식",
        )
        count += 1
    return count


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
    return join_way  # 알 수 없는 패턴이면 원문 그대로 보존


def parse_amount(v):
    if v in (None, 0, "0"):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def process_finlife(filename: str, institution_type: str, product_type_tag: str, parse_conditions: bool):
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
        add_institution(inst_code, kor_co_nm, institution_type, None)

        opts = options_by_product.get((fin_co_no, fin_prdt_cd), [])
        if not opts:
            n_missing_options += 1

        # 적금이면 rsrv_type_nm(자유적립식/정액적립식)별로 그룹 -> 서로 다른 상품(variant)으로 분리.
        # 예금은 rsrv_type_nm 자체가 없으므로 그룹 키가 None 하나뿐이라 분리되지 않는다.
        variants = {}
        for opt in opts:
            variants.setdefault(opt.get("rsrv_type_nm"), []).append(opt)
        if not variants:
            variants = {None: []}
        multi_variant = len([k for k in variants if k]) > 1

        join_channel = classify_join_channel(base.get("join_way"))
        terms_parts = [base.get("mtrt_int"), base.get("etc_note")]
        terms_text = "\n\n".join(p for p in terms_parts if p) or None
        snapshot_date = base.get("dcls_strt_day")
        sale_end_date = base.get("dcls_end_day")
        amount_cap = parse_amount(base.get("max_limit"))

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
                    # optionList에 rsrv_type_nm이 없는 예외 케이스 - 정액적립식으로 가정(확인 필요)
                    p_type = "적금(정액적립식)"
                    product_name = fin_prdt_nm
                    id_suffix = ""

            product_id = f"{inst_code}-{fin_prdt_cd}{id_suffix}"

            add_product(
                product_id,
                institution_code=inst_code,
                product_name=product_name,
                product_type=p_type,
                amount_min=None,
                amount_cap=amount_cap,
                monthly_min=None,
                monthly_cap=None,
                terms_text=terms_text,
                region=None,
                join_channel=join_channel,
                membership_required=None,
                new_customer_only=None,
                min_age=None,
                max_age=None,
                parse_status="PARSED",
                snapshot_date=snapshot_date,
                sale_end_date=sale_end_date,
                is_active=True,
            )

            for opt in opt_rows:
                period_months = parse_term_months(opt.get("save_trm"))
                base_rate = opt.get("intr_rate")
                max_rate = opt.get("intr_rate2")
                if max_rate is None:
                    max_rate = base_rate
                add_product_option(
                    product_id,
                    period_months=period_months,
                    rate_type=rate_type_of(opt.get("intr_rate_type_nm") or "단리"),
                    reserve_type=("거치식" if product_type_tag == "deposit" else (rsrv_key or "정액적립식")),
                    base_rate=base_rate,
                    max_rate=max_rate,
                    snapshot_date=snapshot_date,
                )

            if parse_conditions:
                n_conditions += extract_conditions(product_id, base.get("spcl_cnd"))

    return len(base_list), len(option_list), n_conditions, n_missing_options


FINLIFE_SOURCES = [
    # (파일명, institution_type, product_type_tag, 우대조건 파싱 여부)
    ("deposit_sample.json", "은행", "deposit", True),
    ("saving_sample.json", "은행", "savings", True),
    ("deposit_savingsbank_sample.json", "저축은행", "deposit", False),
    ("saving_savingsbank_sample.json", "저축은행", "savings", False),
]


def main():
    n_cu = process_cu()
    n_kfcc, missing = process_kfcc()

    finlife_summary = []
    for filename, itype, ptag, parse_cond in FINLIFE_SOURCES:
        path = FIXTURES / filename
        if not path.exists():
            finlife_summary.append((filename, None))
            continue
        n_base, n_opt, n_cond, n_missing_opt = process_finlife(filename, itype, ptag, parse_cond)
        finlife_summary.append((filename, (n_base, n_opt, n_cond, n_missing_opt)))

    with (OUT / "institution.jsonl").open("w", encoding="utf-8") as f:
        for row in institutions.values():
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (OUT / "product.jsonl").open("w", encoding="utf-8") as f:
        for row in products.values():
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (OUT / "product_option.jsonl").open("w", encoding="utf-8") as f:
        for row in product_options.values():
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (OUT / "product_condition.jsonl").open("w", encoding="utf-8") as f:
        for row in product_conditions.values():
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"신협 원본 레코드: {n_cu}건, 새마을금고 원본 레코드: {n_kfcc}건")
    print("은행/저축은행(finlife) 원본:")
    for filename, stats in finlife_summary:
        if stats is None:
            print(f"  {filename}: 파일 없음(스킵)")
            continue
        n_base, n_opt, n_cond, n_missing_opt = stats
        print(f"  {filename}: baseList {n_base}건 / optionList {n_opt}건 / 우대조건 추출 {n_cond}건"
              + (f" / 금리옵션 없는 상품 {n_missing_opt}건" if n_missing_opt else ""))
    print()
    print(f"institution: {len(institutions)}건, product: {len(products)}건, "
          f"product_option: {len(product_options)}건, product_condition: {len(product_conditions)}건")
    print(f"중복 option_id: 완전동일(무시) {dup_stats['exact']}건 / 값 충돌(최신 snapshot_date 채택) {dup_stats['conflict']}건")
    if dup_stats["conflict_examples"]:
        print("충돌 예시(최대 10건):")
        for oid, old, new in dup_stats["conflict_examples"]:
            print(f"  {oid}: 기존={old['base_rate']}/{old['max_rate']} -> 새값={new['base_rate']}/{new['max_rate']}")
    if missing:
        print(f"경고: kfcc branches.json에서 못 찾은 지점 {len(missing)}건 -> {missing}")


if __name__ == "__main__":
    main()
