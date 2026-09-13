"""신협 적금(saving_cu_sample.json)에서 실제로 우대조건 텍스트가 있는 1,086건 전체에
Extraction+G3를 돌려서 review_queue를 만든다 - 은행/저축은행과 동일한 완료 상태로 맞추기 위함."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from src.schemas.product import SavingOption
from src.schemas.extraction import ExtractionResult

from openai import OpenAI

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"


def _find_valid(node, model_cls, depth=0):
    if depth > 5:
        return None
    if isinstance(node, dict):
        try:
            return model_cls(**node)
        except Exception:
            pass
        for value in node.values():
            candidate = value
            if isinstance(candidate, str):
                try:
                    candidate = json.loads(candidate)
                except (json.JSONDecodeError, TypeError):
                    continue
            found = _find_valid(candidate, model_cls, depth + 1)
            if found is not None:
                return found
    return None


def parse_structured(raw_text, model_cls):
    data = json.loads(raw_text)
    result = _find_valid(data, model_cls)
    if result is None:
        raise ValueError(f"응답에서 유효한 {model_cls.__name__} 구조를 찾지 못함: {raw_text[:300]}")
    return result


def _condition_applies(cond, term):
    if cond.applicable_term_months is not None:
        return cond.applicable_term_months == term
    if cond.min_term_months is not None:
        return term is not None and term >= cond.min_term_months
    return True


def extract(client, model_name, spcl_cnd_text):
    schema_hint = json.dumps(ExtractionResult.model_json_schema(), ensure_ascii=False)
    system_prompt = (
        "너는 은행 예적금 상품의 우대조건 원문을 분석하는 도우미야.\n\n"
        "작업 순서:\n"
        "1. 원문에서 개별 우대조건과 각 조건의 우대금리(%p)를 원문에 없는 내용은 "
        "지어내지 말고 뽑아.\n"
        "2. 원문에 '최고우대금리'처럼 전체 우대금리의 상한이 명시되어 있으면 이 값을 "
        "반드시 확인해.\n"
        "3. 조건들이 서로 다른 기준(예: '6개월 이상', '12개월 이상')으로 단계별로 커지는 "
        "형태라면, 이건 조건이 누적되는 게 아니라 그 중 하나만 적용되는 거야. 이 경우 "
        "최종 결과에는 실제로 적용되는 최고 단계 조건 하나만 포함시켜.\n"
        "4. 조건이 특정 만기(예: '12개월 신규')에만 정확히 적용된다고 명시돼 있으면, "
        "applicable_term_months에 그 개월 수를 숫자로 넣어.\n"
        "5. 조건이 '12개월 이상'처럼 특정 만기 이상이면 다 적용되는 하한 조건이면, "
        "min_term_months에 그 숫자를 넣어(이 경우 applicable_term_months는 null). "
        "모든 만기에 공통으로 적용되는 조건이면 applicable_term_months와 "
        "min_term_months 둘 다 null로 둬.\n"
        "6. 원문이 '회전시점의 정기예금 금리 + 우대금리 X%'처럼 회전형/변동금리 상품의 "
        "기준금리 자체를 어떻게 산정하는지 설명하는 문구라면, 이건 고객이 별도로 "
        "충족해야 하는 우대조건이 아니라 상품 자체의 금리 산정 공식이야. 이런 경우 "
        "conditions에 포함시키지 마(빈 리스트를 반환해도 돼).\n"
        "7. 원문이 '만기 후 재예치 시', '자동연장 시', '재가입 시'처럼 지금 가입하는 "
        "이 상품이 아니라 향후 재예치·연장 시점에만 적용되는 조건을 설명하면, 이 조건은 "
        "지금 이 상품 옵션에는 적용되지 않으므로 conditions에 포함시키지 마.\n"
        "8. 최종적으로 뽑은 조건들의 우대금리 합계는, 원문에 '최고우대금리'가 명시된 "
        "경우 반드시 그 값과 일치해야 해.\n\n"
        f"반드시 아래 JSON 스키마 형태로만 답해: {schema_hint}"
    )
    res = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": spcl_cnd_text},
        ],
        response_format={"type": "json_object"},
    )
    raw = res.choices[0].message.content
    return parse_structured(raw, ExtractionResult)


def main():
    saving = json.loads((FIXTURES_DIR / "saving_cu_sample.json").read_text(encoding="utf-8"))["result"]
    base_list = saving["baseList"]
    option_list = saving["optionList"]

    candidates = [p for p in base_list if p.get("spcl_cnd") and p.get("spcl_cnd") != "없음"]
    print(f"신협 적금 중 조건 있는 상품: {len(candidates)}건 - Extraction+G3 시작\n")

    client = OpenAI(api_key=OPENAI_API_KEY, base_url=f"{OPENAI_BASE_URL}/v1")

    match_count = 0
    mismatch_count = 0
    fail_count = 0
    review_queue = []

    for i, product in enumerate(candidates, 1):
        fin_co_no = product["fin_co_no"]
        fin_prdt_cd = product["fin_prdt_cd"]
        spcl_cnd = product.get("spcl_cnd", "")
        bank_nm = product.get("kor_co_nm")
        prdt_nm = product.get("fin_prdt_nm")
        dcls_strt_day = product.get("dcls_strt_day")
        dcls_end_day = product.get("dcls_end_day")

        if i % 50 == 0 or i == 1:
            print(f"  진행: {i}/{len(candidates)}건...")

        try:
            parsed = extract(client, OPENAI_MODEL, spcl_cnd)
        except Exception as e:
            fail_count += 1
            review_queue.append({
                "fin_co_no": fin_co_no, "fin_prdt_cd": fin_prdt_cd,
                "fin_prdt_nm": prdt_nm, "kor_co_nm": bank_nm,
                "dcls_strt_day": dcls_strt_day, "dcls_end_day": dcls_end_day,
                "spcl_cnd": spcl_cnd, "status": "EXTRACTION_FAILED",
                "error": str(e), "mismatches": [],
            })
            continue

        matching_options = [
            o for o in option_list
            if o["fin_co_no"] == fin_co_no and o["fin_prdt_cd"] == fin_prdt_cd
        ]

        product_mismatches = []
        for opt in matching_options:
            option = SavingOption(**opt)
            if option.max_bonus is None:
                continue
            try:
                term = int(option.save_trm)
            except ValueError:
                term = None
            applicable_total = round(
                sum(c.bonus_rate for c in parsed.conditions if _condition_applies(c, term)), 4
            )
            if abs(option.max_bonus - applicable_total) >= 0.001:
                product_mismatches.append({
                    "save_trm": option.save_trm,
                    "disclosed_max_bonus": option.max_bonus,
                    "extracted_total": applicable_total,
                    "diff": round(option.max_bonus - applicable_total, 4),
                })

        if product_mismatches:
            mismatch_count += 1
            review_queue.append({
                "fin_co_no": fin_co_no, "fin_prdt_cd": fin_prdt_cd,
                "fin_prdt_nm": prdt_nm, "kor_co_nm": bank_nm,
                "dcls_strt_day": dcls_strt_day, "dcls_end_day": dcls_end_day,
                "spcl_cnd": spcl_cnd, "status": "MISMATCH",
                "extracted_conditions": [c.model_dump() for c in parsed.conditions],
                "mismatches": product_mismatches,
            })
        else:
            match_count += 1

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = LOGS_DIR / "review_queue_cu_saving.json"
    out_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_checked": len(candidates),
                "match_count": match_count,
                "mismatch_count": mismatch_count,
                "fail_count": fail_count,
                "items": review_queue,
            },
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print(f"신협 적금 Extraction+G3 완료: 총 {len(candidates)}건 중 일치 {match_count} / 불일치 {mismatch_count} / 추출실패 {fail_count}")
    print(f"결과 저장: {out_path}")


if __name__ == "__main__":
    main()