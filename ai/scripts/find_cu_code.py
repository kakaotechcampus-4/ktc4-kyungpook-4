"""FSS 정기예금 비교 페이지의 원본 HTML에서 신협조합 필터의 실제 value 값을 찾는 스크립트."""
import re
import requests

URL = "https://finlife.fss.or.kr/finlife/svings/fdrmDpst/list.do?menuNo=700002"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

res = requests.get(URL, headers=headers, timeout=10)
print(f"status_code: {res.status_code}, 길이: {len(res.text)}")

html = res.text

# "신협" 앞뒤 200자씩 보여주기 (여러 번 나오면 전부)
for m in re.finditer("신협", html):
    start = max(0, m.start() - 200)
    end = min(len(html), m.end() + 200)
    print("=" * 40)
    print(html[start:end])

# value="..." 속성이 있는 곳들 중, 숫자 6자리로 된 코드값 후보들 전부 뽑기
print("=" * 40)
print("6자리 숫자 value 후보들:")
codes = sorted(set(re.findall(r'value=["\'](\d{6})["\']', html)))
print(codes)