"""
엘리스 ML API - 모델 전용 엔드포인트에서 실제 model_id를 확인한다.
(base_url + /v1/models 로 GET 요청하면 이 엔드포인트가 서빙하는 모델 정보가 나옴)
"""
import sys
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import OPENAI_API_KEY, OPENAI_BASE_URL_EXTRACTION, OPENAI_BASE_URL_SUMMARY

TARGETS = [
    ("Extraction (GPT-5.4 mini)", OPENAI_BASE_URL_EXTRACTION),
    ("Summary (Claude Sonnet 5)", OPENAI_BASE_URL_SUMMARY),
]


def main():
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }

    for label, base_url in TARGETS:
        if not base_url:
            print(f"[{label}] base_url이 없습니다. .env를 확인하세요.")
            continue

        url = f"{base_url}/v1/models"
        print(f"[{label}] GET {url}")
        try:
            res = requests.get(url, headers=headers, timeout=30)
            print(f"[{label}] status: {res.status_code}")
            print(f"[{label}] body: {res.text}\n")
        except Exception as e:
            print(f"[{label}] 실패: {e}\n")


if __name__ == "__main__":
    main()