"""
Extraction 구조화 출력 테스트 - 실제 spcl_cnd 텍스트 하나를 골라서
GPT-5.4 mini / Claude Sonnet 5 둘 다 Pydantic 스키마로 구조화된 결과를 뽑아낼 수 있는지 확인.
"""
import json
import sys
from pathlib import Path
from typing import List

from pydantic import BaseModel

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL_EXTRACTION,
    OPENAI_BASE_URL_SUMMARY,
    OPENAI_MODEL_EXTRACTION,
    OPENAI_MODEL_SUMMARY,
)

from openai import OpenAI

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


class PreferentialCondition(BaseModel):
    """개별 우대조건 하나"""
    description: str  # 조건 설명 (예: "급여이체 실적 보유")
    bonus_rate: float  # 이 조건으로 얻는 우대금리 (%p 단위, 예: 0.2)


class ExtractionResult(BaseModel):
    """spcl_cnd 원문 하나를 파싱한 결과"""
    conditions: List[PreferentialCondition]


def pick_sample_product():
    """spcl_cnd가 어느정도 길이가 있는(=우대조건이 실제로 있는) 상품 하나를 고른다."""
    path = FIXTURES_DIR / "deposit_savingsbank_sample.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    base_list = data["result"]["baseList"]

    candidates = [p for p in base_list if len(p.get("spcl_cnd", "")) > 30]
    return candidates[0] if candidates else base_list[0]


def run_extraction(label, base_url, model_name, spcl_cnd_text):
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=f"{base_url}/v1")
    print(f"[{label}] 모델: {model_name}")
    try:
        res = client.beta.chat.completions.parse(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 은행 예적금 상품의 우대조건 원문을 분석하는 도우미야. "
                        "주어진 원문에서 개별 우대조건과 그 조건이 주는 우대금리(%p)를 "
                        "빠짐없이, 원문에 없는 내용은 지어내지 말고 추출해."
                    ),
                },
                {"role": "user", "content": spcl_cnd_text},
            ],
            response_format=ExtractionResult,
        )
        parsed = res.choices[0].message.parsed
        print(f"[{label}] 파싱 결과:")
        for cond in parsed.conditions:
            print(f"  - {cond.description}: {cond.bonus_rate}%p")
        print()
    except Exception as e:
        print(f"[{label}] 실패: {e}\n")


def main():
    product = pick_sample_product()
    print("=== 테스트 대상 상품 ===")
    print(f"상품명: {product.get('fin_prdt_nm')}")
    print(f"원문(spcl_cnd): {product.get('spcl_cnd')}\n")

    run_extraction("GPT-5.4 mini", OPENAI_BASE_URL_EXTRACTION, OPENAI_MODEL_EXTRACTION, product.get("spcl_cnd", ""))
    run_extraction("Claude Sonnet 5", OPENAI_BASE_URL_SUMMARY, OPENAI_MODEL_SUMMARY, product.get("spcl_cnd", ""))


if __name__ == "__main__":
    main()