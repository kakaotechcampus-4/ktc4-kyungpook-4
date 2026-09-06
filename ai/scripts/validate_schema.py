"""
정기예금 + 적금, 은행 + 저축은행 - 4개 조합 전부 스키마 검증.
"""
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.schemas.product import ProductBase, ProductOption, SavingOption

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def validate(label, fixture_name, option_model):
    path = FIXTURES_DIR / fixture_name
    if not path.exists():
        print(f"[{label}] 파일 없음: {path}")
        return

    data = json.loads(path.read_text(encoding="utf-8"))
    result = data["result"]

    base_ok, base_fail = 0, []
    for item in result["baseList"]:
        try:
            ProductBase(**item)
            base_ok += 1
        except Exception as e:
            base_fail.append((item.get("fin_prdt_nm"), str(e)))

    opt_ok, opt_fail = 0, []
    for item in result["optionList"]:
        try:
            option_model(**item)
            opt_ok += 1
        except Exception as e:
            opt_fail.append((item.get("fin_prdt_cd"), str(e)))

    print(f"[{label}] ProductBase: {base_ok}/{len(result['baseList'])} 통과")
    for name, err in base_fail[:5]:
        print(f"  실패 - {name}: {err}")

    print(f"[{label}] {option_model.__name__}: {opt_ok}/{len(result['optionList'])} 통과")
    for code, err in opt_fail[:5]:
        print(f"  실패 - {code}: {err}")
    print()


def main():
    validate("은행/정기예금", "deposit_sample.json", ProductOption)
    validate("은행/적금", "saving_sample.json", SavingOption)
    validate("저축은행/정기예금", "deposit_savingsbank_sample.json", ProductOption)
    validate("저축은행/적금", "saving_savingsbank_sample.json", SavingOption)


if __name__ == "__main__":
    main()