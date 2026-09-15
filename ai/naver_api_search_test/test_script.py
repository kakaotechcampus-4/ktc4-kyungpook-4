import json
import requests
import time
from datetime import datetime
from pathlib import Path

CLIENT_ID = "mxcqfwxzmh"
CLIENT_SECRET = "y8ENiiumrJWigUeQknWbh9JNjovmVPebrlf31Ft6"

HEADERS = {
    "X-NCP-APIGW-API-KEY-ID": CLIENT_ID,
    "X-NCP-APIGW-API-KEY": CLIENT_SECRET,
}

RESPONSE_DIR = Path(__file__).parent / "response"

# 2금융권 특판 관련 검색어 조합
KEYWORDS = [
    "지역농협 특판 예금",
    "신협 특판 적금",
    "새마을금고 특판 예금",
    "수협 특판 적금",
]


def search_naver(endpoint: str, query: str, display: int = 100):
    """endpoint: 'cafearticle' 또는 'blog'"""
    url = f"https://naverapihub.apigw.ntruss.com/search/v1/{endpoint}"
    params = {"query": query, "display": display, "sort": "date", "format": "json"}
    res = requests.get(url, headers=HEADERS, params=params)
    if not res.ok:
        print(f"[{res.status_code}] {endpoint} / {query}")
        print(res.text)
        res.raise_for_status()
    return res.json().get("items", [])


def collect_candidates():
    candidates = []
    for keyword in KEYWORDS:
        for endpoint in ["cafearticle", "blog"]:
            items = search_naver(endpoint, keyword)
            for item in items:
                candidates.append({
                    "source": endpoint,
                    "keyword": keyword,
                    "title": item["title"],
                    "link": item["link"],
                    "description": item["description"],
                    "date": item.get("postdate") or item.get("pubDate"),
                })
            time.sleep(0.3)
    return candidates


if __name__ == "__main__":
    results = collect_candidates()
    print(f"총 {len(results)}건 발견")
    for r in results[:10]:
        print(r["title"], "-", r["link"])

    RESPONSE_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESPONSE_DIR / f"result_{timestamp}.json"
    out_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"저장 완료: {out_path}")
