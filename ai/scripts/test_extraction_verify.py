"""
Extraction 결과 검증(G3 검산) - Claude Sonnet 5로 뽑은 우대조건 합계가
실제 공시된 우대폭(intr_rate2 - intr_rate)과 만기별로 맞는지 확인.

불일치/실패 상품은 logs/review_queue.json에 쌓는다.
-> (1) 서비스에 안 나가게 격리할 대상 파악 (2) 프롬프트 개선 자료로 사용
   (3) 은행명 + 공시기간을 같이 저장해서, 공시 종료(판매종료 가능성 높은) 상품과
       실제로 지금도 확인이 필요한 상품을 구분할 수 있게 함.
"""
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from src.schemas.product import ProductOption
from src.schemas.extraction import ExtractionResult

from openai import OpenAI

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"


def _find_valid(node, model_cls, depth=0):
    """어떤 형태로 감싸져 있든, 실제로 model_cls 검증에 성공하는
    딕셔너리를 재귀적으로 찾아서 그 인스턴스를 반환한다."""
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


def parse_structured(raw_text: str, model_cls):
    data = json.loads(raw_text)
    result = _find_valid(data, model_cls)
    if result is None:
        raise ValueError(f"응답에서 유효한 {model_cls.__name__} 구조를 찾지 못함: {raw_text[:300]}")
    return result


def load_products(n=5):
    path = FIXTURES_DIR / "deposit_savingsbank_sample.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    base_list = data["result"]["baseList"]
    option_list = data["result"]["optionList"]

    candidates = [p for p in base_list if len(p.get("spcl_cnd", "")) > 20]
    return candidates[:n], option_list


def _condition_applies(cond, term):
    """이 조건이 주어진 만기(term)에 실제로 적용되는지 판단."""
    if cond.applicable_term_months is not None:
        return cond.applicable_term_months == term
    if cond.min_term_months is not None:
        return term is not None and term >= cond.min_term_months
    return True


def _is_disclosure_stale(dcls_end_day):
    """공시 종료일이 오늘보다 지났으면 True (판매종료/데이터 미관리 가능성)."""
    if not dcls_end_day:
        return False
    try:
        end = date(int(dcls_end_day[:4]), int(dcls_end_day[4:6]), int(dcls_end_day[6:8]))
    except (ValueError, TypeError):
        return False
    return end < date.today()


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
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=f"{OPENAI_BASE_URL}/v1")
    products, option_list = load_products(n=38)

    review_queue = []  # 불일치/실패 케이스 - 격리 + 프롬프트 개선 자료 + 은행명/공시기간 포함

    for product in products:
        fin_co_no = product["fin_co_no"]
        fin_prdt_cd = product["fin_prdt_cd"]
        spcl_cnd = product.get("spcl_cnd", "")
        prdt_nm = product.get("fin_prdt_nm")
        bank_nm = product.get("kor_co_nm")
        dcls_strt_day = product.get("dcls_strt_day")
        dcls_end_day = product.get("dcls_end_day")
        is_stale = _is_disclosure_stale(dcls_end_day)

        print("=" * 60)
        print(f"은행: {bank_nm} / 상품명: {prdt_nm}")
        print(f"원문: {spcl_cnd}")

        try:
            parsed = extract(client, OPENAI_MODEL, spcl_cnd)
        except Exception as e:
            print(f"추출 실패: {e}\n")
            review_queue.append({
                "fin_co_no": fin_co_no,
                "fin_prdt_cd": fin_prdt_cd,
                "fin_prdt_nm": prdt_nm,
                "kor_co_nm": bank_nm,
                "dcls_strt_day": dcls_strt_day,
                "dcls_end_day": dcls_end_day,
                "is_disclosure_stale": is_stale,
                "spcl_cnd": spcl_cnd,
                "status": "EXTRACTION_FAILED",
                "error": str(e),
                "mismatches": [],
            })
            continue

        print("추출된 조건:")
        for cond in parsed.conditions:
            if cond.applicable_term_months:
                term_note = f" (만기 {cond.applicable_term_months}개월 전용)"
            elif cond.min_term_months:
                term_note = f" (만기 {cond.min_term_months}개월 이상 적용)"
            else:
                term_note = ""
            print(f"  - {cond.description}: {cond.bonus_rate}%p{term_note}")

        matching_options = [
            o for o in option_list
            if o["fin_co_no"] == fin_co_no and o["fin_prdt_cd"] == fin_prdt_cd
        ]

        product_mismatches = []
        for opt in matching_options:
            option = ProductOption(**opt)
            try:
                term = int(option.save_trm)
            except ValueError:
                term = None

            applicable_total = round(
                sum(c.bonus_rate for c in parsed.conditions if _condition_applies(c, term)),
                4,
            )
            is_match = abs(option.max_bonus - applicable_total) < 0.001
            mark = "일치" if is_match else "불일치"
            print(
                f"  [만기 {option.save_trm}개월] 공시 우대폭={option.max_bonus}%p, "
                f"적용조건합계={applicable_total}%p -> {mark}"
            )
            if not is_match:
                product_mismatches.append({
                    "save_trm": option.save_trm,
                    "disclosed_max_bonus": option.max_bonus,
                    "extracted_total": applicable_total,
                    "diff": round(option.max_bonus - applicable_total, 4),
                })

        if product_mismatches:
            review_queue.append({
                "fin_co_no": fin_co_no,
                "fin_prdt_cd": fin_prdt_cd,
                "fin_prdt_nm": prdt_nm,
                "kor_co_nm": bank_nm,
                "dcls_strt_day": dcls_strt_day,
                "dcls_end_day": dcls_end_day,
                "is_disclosure_stale": is_stale,
                "spcl_cnd": spcl_cnd,
                "status": "MISMATCH",
                "extracted_conditions": [c.model_dump() for c in parsed.conditions],
                "mismatches": product_mismatches,
            })
        print()

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    review_path = LOGS_DIR / "review_queue.json"
    stale_count = sum(1 for item in review_queue if item.get("is_disclosure_stale"))
    review_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_checked": len(products),
                "review_count": len(review_queue),
                "stale_count": stale_count,
                "items": review_queue,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 60)
    print(f"검증 완료: 총 {len(products)}개 중 격리 대상 {len(review_queue)}개 (공시 종료 추정 {stale_count}개)")
    print(f"격리 목록 저장 위치: {review_path}")


if __name__ == "__main__":
    main()