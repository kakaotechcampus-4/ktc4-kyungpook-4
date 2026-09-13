"""
농협 nhInfo.do 진단용: 브라우저로는 정상 데이터가 오는데 requests로는 0건이 나온 원인을 확인.
실제로 받은 응답의 길이/앞부분/상태코드/리다이렉트 여부를 그대로 출력한다.
"""
import requests

URL = "https://www.nonghyup.com/introduce/organization/nhInfo.do"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": URL,
    "Origin": "https://www.nonghyup.com",
}

session = requests.Session()
r0 = session.get(URL, headers=HEADERS, timeout=20)
print("GET status:", r0.status_code, "len:", len(r0.text), "history:", r0.history)
print("GET에 '농협' 포함:", "농협" in r0.text, " / '1,281' 포함:", "1,281" in r0.text)
print("쿠키:", session.cookies.get_dict())
print()

r1 = session.post(
    URL,
    data={"pageIndex": "1", "indexRegion": "entire", "searchCcwnm": "", "searchWrd": ""},
    headers=HEADERS,
    timeout=20,
)
print("POST status:", r1.status_code, "len:", len(r1.text), "history:", r1.history)
print("POST에 '농협' 포함:", "농협" in r1.text, " / '<table' 개수:", r1.text.count("<table"))
print("POST 응답 앞부분 1500자:")
print(r1.text[:1500])