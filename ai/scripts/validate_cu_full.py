"""신협 전체 데이터(deposit_cu_sample.json, saving_cu_sample.json)를 대상으로
스키마 전량 검증 + spcl_cnd/우대폭 패턴을 확정 확인."""
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.schemas.product import ProductBase, ProductOption, SavingOption

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def validate(base_list, option_list, option_model, label):
    base_fail = []
    for item in base_list:
        try:
            ProductBase(**item)
        except Exception as e:
            base_fail.append((item.get("fin_prdt_cd"), str(e)[:150]))

    opt_fail = []
    for item in option_list:
        try:
            option_model(**item)
        except Exception as e:
            opt_fail.append((item.get("fin_prdt_cd"), str(e)[:150]))

    print(f"[{label}] baseList {len(base_list)}건 중 스키마 실패 {len(base_fail)}건")
    for f in base_fail[:5]:
        print(f"    - {f}")
    print(f"[{label}] optionList {len(option_list)}건 중 스키마 실패 {len(opt_fail)}건")
    for f in opt_fail[:5]:
        print(f"    - {f}")

    # spcl_cnd 패턴
    non_empty_cnd = [p for p in base_list if p.get("spcl_cnd") and p.get("spcl_cnd") != "없음"]
    print(f"[{label}] spcl_cnd가 '없음'이 아닌 상품: {len(non_empty_cnd)}건 / 전체 {len(base_list)}건")

    # 우대폭 존재 여부(intr_rate2 > intr_rate)
    has_bonus = 0
    for opt in option_list:
        ir, ir2 = opt.get("intr_rate"), opt.get("intr_rate2")
        if ir is None or ir2 is None:
            continue
        if round(ir2 - ir, 4) > 0.001:
            has_bonus += 1
    print(f"[{label}] 우대폭(intr_rate2>intr_rate) 존재 옵션: {has_bonus}건 / 전체 {len(option_list)}건\n")


def main():
    deposit = json.loads((FIXTURES_DIR / "deposit_cu_sample.json").read_text(encoding="utf-8"))["result"]
    saving = json.loads((FIXTURES_DIR / "saving_cu_sample.json").read_text(encoding="utf-8"))["result"]

    validate(deposit["baseList"], deposit["optionList"], ProductOption, "신협 정기예금(전체)")
    validate(saving["baseList"], saving["optionList"], SavingOption, "신협 적금(전체)")


if __name__ == "__main__":
    main()