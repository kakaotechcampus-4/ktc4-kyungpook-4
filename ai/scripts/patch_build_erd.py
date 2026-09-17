"""
build_erd_tables.py의 attach_ai_conditions()만 콕 집어서 고치는 패치 스크립트.
(파일 전체를 다시 안 보내고, 이 부분만 정확히 찾아서 바꿔치기)

바뀌는 내용: extract_conditions_ai.py에 max_term_months(만기 상한)가 추가됐으니,
product_condition의 apply_period_min/apply_period_max를 "정확히 X개월이면 둘 다 X,
아니면 min/max 그대로"로 정리해주는 _period_bounds() 헬퍼를 추가하고 그걸 쓰도록 바꿈.
"""
from pathlib import Path

p = Path("scripts/build_erd_tables.py")
text = p.read_text(encoding="utf-8")

old = """def attach_ai_conditions(ai_cache, filename, fin_co_no, fin_prdt_cd, product_id) -> int:
    \"\"\"extract_conditions_ai.py가 만든 캐시에서 이 상품(base)의 AI 추출 결과를 찾아
    product_condition 행으로 채운다. 캐시에 없거나(=아직 AI extraction을 안 돌림) 그 상품
    호출이 실패했으면(error 있음) 아무것도 채우지 않고 0을 반환한다.\"\"\"
    key = f"{filename}:{fin_co_no}:{fin_prdt_cd}"
    row = ai_cache.get(key)
    if not row or row.get("error"):
        return 0
    status = row["verification_status"]
    confidence_badge = {"MATCHED": "HIGH", "MISMATCH": "LOW"}.get(status, status)
    count = 0
    for cond in row["conditions"]:
        add_product_condition(
            product_id,
            condition_type=classify_condition_type(cond["description"]),
            rate_bonus=cond.get("bonus_rate"),
            evidence_text=cond["description"],
            evidence_url=row.get("evidence_url"),
            verification_status=status,
            confidence_badge=confidence_badge,
            apply_period_min=cond.get("min_term_months"),
            apply_period_max=cond.get("applicable_term_months"),
        )
        count += 1
    return count"""

new = """def _period_bounds(cond):
    \"\"\"AI가 뽑은 만기 적용범위(정확히 X개월 / X개월 이상 / X개월 이하 / X~Y개월)를
    product_condition의 apply_period_min/apply_period_max 두 컬럼으로 정리.\"\"\"
    exact = cond.get("applicable_term_months")
    if exact is not None:
        return exact, exact
    return cond.get("min_term_months"), cond.get("max_term_months")


def attach_ai_conditions(ai_cache, filename, fin_co_no, fin_prdt_cd, product_id) -> int:
    \"\"\"extract_conditions_ai.py가 만든 캐시에서 이 상품(base)의 AI 추출 결과를 찾아
    product_condition 행으로 채운다. 캐시에 없거나(=아직 AI extraction을 안 돌림) 그 상품
    호출이 실패했으면(error 있음) 아무것도 채우지 않고 0을 반환한다.\"\"\"
    key = f"{filename}:{fin_co_no}:{fin_prdt_cd}"
    row = ai_cache.get(key)
    if not row or row.get("error"):
        return 0
    status = row["verification_status"]
    confidence_badge = {"MATCHED": "HIGH", "MISMATCH": "LOW"}.get(status, status)
    count = 0
    for cond in row["conditions"]:
        apply_period_min, apply_period_max = _period_bounds(cond)
        add_product_condition(
            product_id,
            condition_type=classify_condition_type(cond["description"]),
            rate_bonus=cond.get("bonus_rate"),
            evidence_text=cond["description"],
            evidence_url=row.get("evidence_url"),
            verification_status=status,
            confidence_badge=confidence_badge,
            apply_period_min=apply_period_min,
            apply_period_max=apply_period_max,
        )
        count += 1
    return count"""

count = text.count(old)
if count != 1:
    print(f"[!] 패턴이 {count}번 발견됨(1번이어야 정상) - 파일이 예상과 달라서 패치를 못 했습니다.")
    print("    이 경우 build_erd_tables.py 전체를 다시 보내달라고 하겠습니다.")
else:
    p.write_text(text.replace(old, new), encoding="utf-8")
    print("패치 완료: attach_ai_conditions()가 max_term_months(만기 상한)까지 반영하도록 바뀜")