"""
새마을금고중앙회(kfcc.co.kr) 전국 지점 디렉토리 수집.

kfcc.co.kr/map/list.do?r1=<시도>&r2=<시군구> 를 지역별로 GET 하면
해당 지역의 모든 지점이 이미 한 번에(숨김 span 형태로) 응답에 들어있음
(페이지네이션은 프론트에서 display:none 토글만 하는 것이라 추가 요청 불필요 - 브라우저로 실제 확인함).

각 <tr> 안에 <span hidden title="필드명">값</span> 형태로
gmgoCd(지점코드), name, gmgoNm, divCd(지점구분코드), divNm(구분명: 본점/지점 등),
gmgoType(지역/직장), telephone, fax, addr, r1, r2, code1, code2 가 들어있음.
이 gmgoCd 값이 다음 단계(fetch_kfcc_rates.py)에서 금리 조회에 그대로 쓰임.

[저장 방식 - 금리와 한 묶음으로 교체]
지점 목록과 지점별 금리(kfcc_rates.jsonl)는 ERD 빌드에서 서로 이어 붙여 쓰므로 같은 실행의 것이어야 한다.
그래서 이 스크립트는 kfcc_branches.json 을 바로 바꾸지 않고 kfcc_branches.json.next 에만 저장한다.
fetch_kfcc_rates.py 가 이 .next 로 금리를 받고, 금리까지 성공하면 두 파일을 함께 교체한다.
(금리가 실패하면 .next 를 지우고 두 파일 모두 지난 수집본을 유지한다)
실패로 보는 경우: 목록 페이지 접속 오류, 실패한 지역을 끝에 한 번 더 시도해도 남은 실패가 있을 때, 전체 0건.
지역 하나가 실패하면 그 지역 지점이 통째로 빠지므로 한 곳이라도 남으면 실패로 본다.
(오류 없이 0건인 지역은 정상 - 지점이 없는 지역일 수 있다)
"""
import json
import os
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / "kfcc_branches.json"
# 다음 수집본. fetch_kfcc_rates.py 가 금리까지 성공하면 OUT_PATH 로 옮긴다
NEXT_PATH = OUT_DIR / "kfcc_branches.json.next"
TMP_PATH = OUT_DIR / "kfcc_branches.json.next.tmp"

BASE_URL = "https://www.kfcc.co.kr/map/list.do"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.kfcc.co.kr/map/main.do",
}

# regionSet() 자바스크립트 함수에서 그대로 추출한 시도->시군구 목록
REGIONS = {
    "서울": ["도봉구","마포구","관악구","강북구","용산구","서초구","노원구","성동구","강남구","성북구",
            "광진구","송파구","은평구","강서구","강동구","종로구","양천구","중랑구","영등포구","서대문구",
            "구로구","동대문구","동작구","중구","금천구"],
    "인천": ["강화군","서해구","검단구","영종구","제물포구","미추홀구","연수구","계양구","부평구","남동구","옹진군"],
    "경기": ["김포시","파주시","연천군","고양시","양주시","동두천시","포천시","의정부시","남양주시","구리시",
            "가평군","하남시","부천시","광명시","시흥시","안산시","안양시","과천시","군포시","의왕시",
            "성남시","광주시","양평군","화성시","수원시","오산시","용인시","이천시","여주시","평택시","안성시"],
    "강원": ["철원군","화천군","양구군","춘천시","인제군","고성군","속초시","양양군","홍천군","강릉시",
            "원주시","횡성군","평창군","영월군","정선군","동해시","삼척시","태백시"],
    "충남": ["태안군","서산시","당진시","홍성군","예산군","아산시","천안시","보령시","청양군","공주시",
            "서천군","부여군","논산시","금산군","계룡시"],
    "충북": ["청주시","진천군","음성군","충주시","제천시","괴산군","단양군","보은군","옥천군","영동군","증평군"],
    "대전": ["유성구","대덕구","서구","중구","동구"],
    "경북": ["문경시","예천군","영주시","봉화군","울진군","상주시","의성군","안동시","영양군","김천시",
            "구미시","청송군","영덕군","성주군","칠곡군","영천시","포항시","고령군","경산시","경주시",
            "청도군","울릉군"],
    "대구": ["서구","북구","동구","달서구","중구","남구","수성구","달성군","군위군"],
    "부산": ["강서구","북구","금정구","기장군","사상구","부산진구","연제구","동래구","사하구","서구",
            "중구","동구","남구","수영구","해운대구","영도구"],
    "울산": ["울주군","북구","중구","남구","동구"],
    "전북": ["군산시","익산시","부안군","김제시","완주군","전주시","고창군","정읍시","순창군","임실군",
            "진안군","무주군","남원시","장수군"],
    "광주": ["목포시","여수시","순천시","나주시","광양시","동구","서구","남구","북구","광산구",
              "담양군","곡성군","구례군","고흥군","보성군","화순군","장흥군","강진군","해남군","영암군",
              "무안군","함평군","영광군","장성군","완도군","진도군","신안군"],
    "경남": ["함양군","거창군","산청군","합천군","하동군","진주시","의령군","함안군","창녕군","남해군",
              "사천시","고성군","창원시","밀양시","통영시","거제시","김해시","양산시"],
    "제주": ["제주시","서귀포시"],
    "세종": [""],
}


def parse_branches(html: str, r1: str, r2: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table tbody tr")
    out = []
    for tr in rows:
        spans = tr.select("span[title]")
        if not spans:
            continue
        rec = {sp.get("title"): sp.get_text(strip=True) for sp in spans}
        if rec.get("gmgoCd"):
            out.append(rec)
    return out


_ERROR_BODY_SHOWN = False  # 오류 응답 본문은 한 번만 출력


def fetch_region(session: requests.Session, r1: str, r2: str) -> list[dict]:
    resp = session.get(BASE_URL, params={"r1": r1, "r2": r2}, headers=HEADERS, timeout=20)
    global _ERROR_BODY_SHOWN
    if resp.status_code != 200 and not _ERROR_BODY_SHOWN:
        _ERROR_BODY_SHOWN = True
        print(f"  [응답 {resp.status_code} 본문 앞부분] {resp.text[:300]!r}")
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return parse_branches(resp.text, r1, r2)


def _fail(reason):
    """파일을 바꾸지 않고 끝낸다(지난 수집본 유지). 지난 실행이 남긴 .next 도 지워 금리 단계가 쓰지 않게 한다."""
    NEXT_PATH.unlink(missing_ok=True)
    TMP_PATH.unlink(missing_ok=True)
    print(f"{reason} - 실패로 처리. 기존 지점 목록을 유지합니다.")
    sys.exit(1)


def main():
    session = requests.Session()
    try:
        session.get("https://www.kfcc.co.kr/map/main.do", headers=HEADERS, timeout=20)
    except requests.RequestException as e:
        _fail(f"메인 페이지 접속 오류: {e}")

    by_region: dict[tuple[str, str], list[dict]] = {}
    regions = [(r1, r2) for r1, districts in REGIONS.items() for r2 in districts]

    failed = []
    for done, (r1, r2) in enumerate(regions, 1):
        try:
            by_region[(r1, r2)] = fetch_region(session, r1, r2)
        except requests.RequestException as e:
            print(f"  [{done}/{len(regions)}] {r1} {r2} 실패: {e}")
            failed.append((r1, r2))
            continue
        print(f"  [{done}/{len(regions)}] {r1} {r2}: {len(by_region[(r1, r2)])}건")
        time.sleep(0.3)

    # 실패한 지역은 끝에 한 번 더 시도한다 (일시적인 오류일 수 있어서)
    still_failed = []
    if failed:
        print(f"\n실패한 지역 {len(failed)}곳 재시도")
    for r1, r2 in failed:
        try:
            by_region[(r1, r2)] = fetch_region(session, r1, r2)
            print(f"  [재시도] {r1} {r2}: {len(by_region[(r1, r2)])}건")
        except requests.RequestException as e:
            print(f"  [재시도] {r1} {r2} 또 실패: {e}")
            still_failed.append((r1, r2))
        time.sleep(0.3)
    if still_failed:
        _fail(f"재시도 후에도 실패한 지역 {len(still_failed)}곳: {still_failed[:10]}")

    # 지역 순서대로 합친다 (재시도한 지역도 원래 자리에)
    all_branches = [b for region in regions for b in by_region[region]]
    if not all_branches:
        _fail("지점 0건 수집")

    try:
        TMP_PATH.write_text(json.dumps(all_branches, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(TMP_PATH, NEXT_PATH)
    except OSError as e:
        _fail(f"임시 파일 저장 실패: {e}")
    print(f"\n총 {len(all_branches)}개 지점 수집 완료 -> {NEXT_PATH} (금리 수집까지 성공하면 {OUT_PATH.name} 로 교체)")

    unique_codes = {b["gmgoCd"] for b in all_branches}
    print(f"고유 gmgoCd 수: {len(unique_codes)}개 (다음 단계 금리조회 대상)")


if __name__ == "__main__":
    main()