"""
엘리스 ML API 실제 채팅 호출 테스트 - 호출 A(Extraction), 호출 B(Summary) 각각 확인.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL_EXTRACTION,
    OPENAI_BASE_URL_SUMMARY,
    OPENAI_MODEL_EXTRACTION,
    OPENAI_MODEL_SUMMARY,
)

from openai import OpenAI


def test_model(label, base_url, model_name):
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=f"{base_url}/v1")
    print(f"[{label}] 모델: {model_name} 호출 중...")

    # GPT-5 계열은 max_tokens 대신 max_completion_tokens를 요구함
    token_param = "max_completion_tokens" if "gpt-5" in model_name else "max_tokens"
    kwargs = {token_param: 100}

    try:
        res = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "딱 한 문장으로 대답해줘: 너는 어떤 모델이야?"}],
            **kwargs,
        )
        answer = res.choices[0].message.content
        print(f"[{label}] 응답: {answer}\n")
    except Exception as e:
        print(f"[{label}] 실패: {e}\n")


def main():
    test_model("호출 A (Extraction)", OPENAI_BASE_URL_EXTRACTION, OPENAI_MODEL_EXTRACTION)
    test_model("호출 B (Summary)", OPENAI_BASE_URL_SUMMARY, OPENAI_MODEL_SUMMARY)


if __name__ == "__main__":
    main()