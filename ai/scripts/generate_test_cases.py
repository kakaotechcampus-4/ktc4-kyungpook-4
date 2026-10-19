#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
티어 비교 테스트용 더미 유저 입력 300건 생성 → test_cases.json

[생성 그룹]
  A. 목돈만 (금액 × 기간)                    32건
  B. 월저축만 (금액 × 기간)                   20건
  C. 목돈 + 월저축 복합                       48건
  D. 균형형 조건 27가지 (3^3 조합)            27건
  E. 세금 조건 다양화                         24건
  F. 예금자보호 한도 초과 (1억+)              20건
  G. CU(신협) 기관별 main_bank              30건
  H. KFCC(새마을금고) 기관별 main_bank      30건
  I. main_bank 없는 케이스                   20건
  J. 엣지 케이스                             49건
  K. 은행·저축은행 주거래 (단순형 검증)       40건
  총계: 340건

[실행]
  python generate_test_cases.py
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

OUT_PATH = Path(__file__).parent / "test_cases.json"

# ---------------------------------------------------------------------------
# 실제 institution.jsonl 에서 샘플링한 institution_code
# ---------------------------------------------------------------------------
CU_CODES = [
    "CU-07005", "CU-07102", "CU-03195", "CU-08117", "CU-10105",
    "CU-06016", "CU-06047", "CU-01189", "CU-10143", "CU-02022",
]
KFCC_CODES = [
    "KFCC-5509-001", "KFCC-3850-001", "KFCC-3334-001", "KFCC-5626-001",
    "KFCC-1030-001", "KFCC-1205-001", "KFCC-5122-001", "KFCC-1444-001",
    "KFCC-0623-001", "KFCC-3120-001",
]
BANK_CODES = {
    "국민": "BANK-0010927",
    "신한": "BANK-0011625",
    "하나": "BANK-0013909",
    "우리": "BANK-0010001",
    "농협": "BANK-0013175",
    "기업": "BANK-0010026",
    "수협": "BANK-0014807",
    "경남": "BANK-0010024",
    "카카오": "BANK-0015130",
    "토스": "BANK-0017801",
}
SB_CODES = {
    "SBI":    "SB-0010370",
    "OK":     "SB-0013351",
    "웰컴":   "SB-0013350",
    "한국투자": "SB-0010537",
    "KB저축": "SB-0013127",
    "신한저축": "SB-0013313",
    "하나저축": "SB-0013166",
}

# ---------------------------------------------------------------------------
# 빌더
# ---------------------------------------------------------------------------
_counter = 0

def case(
    label: str,
    capital: int,
    monthly_saving: int,
    period_months: int,
    main_bank_code: str | None,
    *,
    marketing_consent: bool | None = True,
    app_install: bool | None = True,
    auto_transfer: bool | None = True,
    accepts_membership: bool | None = True,
    coop_tax_eligible: bool | None = True,
    coop_exempt_used: int = 0,
) -> dict:
    global _counter
    _counter += 1
    return {
        "id": _counter,
        "label": label,
        "capital": capital,
        "monthly_saving": monthly_saving,
        "period_months": period_months,
        "main_bank_code": main_bank_code,
        "marketing_consent": marketing_consent,
        "app_install": app_install,
        "auto_transfer": auto_transfer,
        "accepts_membership": accepts_membership,
        "coop_tax_eligible": coop_tax_eligible,
        "coop_exempt_used": coop_exempt_used,
    }


# ---------------------------------------------------------------------------
# A. 목돈만 (기본 조건) — 8 금액 × 4 기간 = 32건
# ---------------------------------------------------------------------------
def group_a() -> list[dict]:
    capitals = [1_000_000, 5_000_000, 10_000_000, 30_000_000,
                50_000_000, 100_000_000, 150_000_000, 200_000_000]
    periods  = [3, 6, 12, 36]
    result = []
    bank = CU_CODES[0]
    for i, (cap, period) in enumerate(itertools.product(capitals, periods)):
        result.append(case(
            f"A{i+1:02d}_목돈{cap//10000:,}만_기간{period}개월",
            capital=cap, monthly_saving=0, period_months=period,
            main_bank_code=bank,
        ))
    return result  # 32건


# ---------------------------------------------------------------------------
# B. 월저축만 (기본 조건) — 5 금액 × 4 기간 = 20건
# ---------------------------------------------------------------------------
def group_b() -> list[dict]:
    monthlys = [100_000, 300_000, 500_000, 700_000, 1_000_000]
    periods  = [6, 12, 24, 36]
    result = []
    bank = CU_CODES[1]
    for i, (m, period) in enumerate(itertools.product(monthlys, periods)):
        result.append(case(
            f"B{i+1:02d}_월저축{m//10000:,}만_기간{period}개월",
            capital=0, monthly_saving=m, period_months=period,
            main_bank_code=bank,
        ))
    return result  # 20건


# ---------------------------------------------------------------------------
# C. 목돈 + 월저축 복합 — 4 cap × 4 monthly × 3 period = 48건
# ---------------------------------------------------------------------------
def group_c() -> list[dict]:
    capitals = [10_000_000, 30_000_000, 50_000_000, 100_000_000]
    monthlys = [100_000, 300_000, 500_000, 1_000_000]
    periods  = [6, 12, 36]
    result = []
    bank = CU_CODES[2]
    for i, (cap, m, period) in enumerate(itertools.product(capitals, monthlys, periods)):
        result.append(case(
            f"C{i+1:03d}_목돈{cap//10000:,}만+월{m//10000:,}만_기간{period}개월",
            capital=cap, monthly_saving=m, period_months=period,
            main_bank_code=bank,
        ))
    return result  # 48건


# ---------------------------------------------------------------------------
# D. 균형형 조건 3^3 = 27가지 조합 (목돈 5천만, 12개월)
# ---------------------------------------------------------------------------
def group_d() -> list[dict]:
    bools = [True, False, None]
    result = []
    bank = CU_CODES[3]
    for i, (mc, ai, at) in enumerate(itertools.product(bools, bools, bools)):
        mc_str = {True: "동의", False: "거부", None: "모름"}[mc]
        ai_str = {True: "가능", False: "불가", None: "모름"}[ai]
        at_str = {True: "가능", False: "불가", None: "모름"}[at]
        result.append(case(
            f"D{i+1:02d}_마케팅{mc_str}_앱{ai_str}_자동이체{at_str}",
            capital=50_000_000, monthly_saving=0, period_months=12,
            main_bank_code=bank,
            marketing_consent=mc, app_install=ai, auto_transfer=at,
        ))
    return result  # 27건


# ---------------------------------------------------------------------------
# E. 세금 조건 다양화 — accepts(3) × coop_eligible(2) × exempt_used(4) = 24건
# ---------------------------------------------------------------------------
def group_e() -> list[dict]:
    accepts  = [True, False, None]
    eligible = [True, False]
    used     = [0, 10_000_000, 20_000_000, 30_000_000]
    result = []
    bank = KFCC_CODES[0]
    for i, (acc, elig, u) in enumerate(itertools.product(accepts, eligible, used)):
        acc_str  = {True: "가입", False: "거부", None: "모름"}[acc]
        elig_str = {True: "저율", False: "일반"}[elig]
        result.append(case(
            f"E{i+1:02d}_조합원{acc_str}_과세{elig_str}_감면사용{u//10000:,}만",
            capital=30_000_000, monthly_saving=0, period_months=12,
            main_bank_code=bank,
            accepts_membership=acc, coop_tax_eligible=elig, coop_exempt_used=u,
        ))
    return result  # 24건


# ---------------------------------------------------------------------------
# F. 예금자보호 한도 초과 (1억~2억) — 4 cap × 5 기간조합 = 20건
# ---------------------------------------------------------------------------
def group_f() -> list[dict]:
    capitals = [110_000_000, 130_000_000, 150_000_000, 200_000_000]
    periods  = [3, 6, 12, 24, 36]
    result = []
    for i, (cap, period) in enumerate(itertools.product(capitals, periods)):
        bank = CU_CODES[i % len(CU_CODES)]
        result.append(case(
            f"F{i+1:02d}_한도초과{cap//10000:,}만_기간{period}개월",
            capital=cap, monthly_saving=0, period_months=period,
            main_bank_code=bank,
        ))
    return result  # 20건


# ---------------------------------------------------------------------------
# G. CU(신협) 기관별 — 10 codes × 3 시나리오 = 30건
# ---------------------------------------------------------------------------
def group_g() -> list[dict]:
    scenarios = [
        (50_000_000, 0, 12),
        (0, 500_000, 12),
        (30_000_000, 300_000, 24),
    ]
    result = []
    for i, (code, (cap, m, period)) in enumerate(itertools.product(CU_CODES, scenarios)):
        result.append(case(
            f"G{i+1:02d}_CU_{code}_목돈{cap//10000:,}만_월{m//10000:,}만_기간{period}개월",
            capital=cap, monthly_saving=m, period_months=period,
            main_bank_code=code,
        ))
    return result  # 30건


# ---------------------------------------------------------------------------
# H. KFCC(새마을금고) 기관별 — 10 codes × 3 시나리오 = 30건
# ---------------------------------------------------------------------------
def group_h() -> list[dict]:
    scenarios = [
        (50_000_000, 0, 12),
        (0, 500_000, 12),
        (30_000_000, 300_000, 24),
    ]
    result = []
    for i, (code, (cap, m, period)) in enumerate(itertools.product(KFCC_CODES, scenarios)):
        result.append(case(
            f"H{i+1:02d}_KFCC_{code}_목돈{cap//10000:,}만_월{m//10000:,}만_기간{period}개월",
            capital=cap, monthly_saving=m, period_months=period,
            main_bank_code=code,
        ))
    return result  # 30건


# ---------------------------------------------------------------------------
# I. main_bank 없는 케이스 — 20건
# ---------------------------------------------------------------------------
def group_i() -> list[dict]:
    configs = [
        (10_000_000, 0, 6),
        (30_000_000, 0, 12),
        (50_000_000, 0, 12),
        (100_000_000, 0, 12),
        (150_000_000, 0, 12),
        (0, 100_000, 12),
        (0, 300_000, 12),
        (0, 500_000, 24),
        (0, 1_000_000, 36),
        (10_000_000, 100_000, 12),
        (30_000_000, 300_000, 12),
        (50_000_000, 500_000, 24),
        (100_000_000, 300_000, 36),
        (50_000_000, 0, 36),
        (200_000_000, 0, 12),
        (50_000_000, 0, 12),
        (30_000_000, 0, 6),
        (10_000_000, 500_000, 12),
        (20_000_000, 200_000, 24),
        (80_000_000, 0, 12),
    ]
    result = []
    for i, (cap, m, period) in enumerate(configs):
        result.append(case(
            f"I{i+1:02d}_주거래없음_목돈{cap//10000:,}만_월{m//10000:,}만_기간{period}개월",
            capital=cap, monthly_saving=m, period_months=period,
            main_bank_code=None,
        ))
    return result  # 20건


# ---------------------------------------------------------------------------
# J. 엣지 케이스 — 49건
# ---------------------------------------------------------------------------
def group_j() -> list[dict]:
    result = []

    # 최소 기간 1개월
    for i, code in enumerate(CU_CODES[:5]):
        result.append(case(
            f"J{len(result)+1:02d}_최소기간1개월_목돈{(i+1)*10:,}만",
            capital=(i+1)*1_000_000, monthly_saving=0, period_months=1,
            main_bank_code=code,
        ))

    # 최장 기간 36개월 × 다양한 자산
    for cap in [10_000_000, 30_000_000, 50_000_000, 100_000_000]:
        result.append(case(
            f"J{len(result)+1:02d}_최장기간36개월_목돈{cap//10000:,}만",
            capital=cap, monthly_saving=0, period_months=36,
            main_bank_code=CU_CODES[4],
        ))

    # 조합원 거부 (신협/새마을금고 접근 불가)
    for i, (cap, period) in enumerate([(50_000_000, 12), (100_000_000, 12), (30_000_000, 24)]):
        result.append(case(
            f"J{len(result)+1:02d}_조합원거부_목돈{cap//10000:,}만_기간{period}개월",
            capital=cap, monthly_saving=0, period_months=period,
            main_bank_code=CU_CODES[0],
            accepts_membership=False,
        ))

    # 감면 한도 소진 (coop_exempt_used=3천만)
    for cap in [30_000_000, 50_000_000, 100_000_000]:
        result.append(case(
            f"J{len(result)+1:02d}_감면한도소진_목돈{cap//10000:,}만",
            capital=cap, monthly_saving=0, period_months=12,
            main_bank_code=KFCC_CODES[0],
            coop_exempt_used=30_000_000,
        ))

    # 모든 조건 모름 (None)
    for period in [6, 12, 24]:
        result.append(case(
            f"J{len(result)+1:02d}_모든조건모름_기간{period}개월",
            capital=50_000_000, monthly_saving=0, period_months=period,
            main_bank_code=CU_CODES[2],
            marketing_consent=None, app_install=None, auto_transfer=None,
            accepts_membership=None, coop_tax_eligible=None,
        ))

    # 고소득자 (coop_tax_eligible=False, 저율과세 미적용)
    for cap in [50_000_000, 100_000_000, 150_000_000]:
        result.append(case(
            f"J{len(result)+1:02d}_고소득자_목돈{cap//10000:,}만",
            capital=cap, monthly_saving=0, period_months=12,
            main_bank_code=KFCC_CODES[1],
            coop_tax_eligible=False,
        ))

    # 목돈 0 + 월저축 0 (결과 없어야 함)
    result.append(case(
        f"J{len(result)+1:02d}_자산없음_edge",
        capital=0, monthly_saving=0, period_months=12,
        main_bank_code=CU_CODES[0],
    ))

    # 극소액 (1만원)
    result.append(case(
        f"J{len(result)+1:02d}_극소액1만원_기간12개월",
        capital=10_000, monthly_saving=0, period_months=12,
        main_bank_code=CU_CODES[0],
    ))

    # CU + 조합원 + 저율 + 감면한도 일부 사용
    for used in [0, 10_000_000, 20_000_000, 25_000_000, 30_000_000]:
        result.append(case(
            f"J{len(result)+1:02d}_CU_감면한도잔여{(30_000_000-used)//10000:,}만",
            capital=50_000_000, monthly_saving=0, period_months=12,
            main_bank_code=CU_CODES[5],
            accepts_membership=True, coop_tax_eligible=True, coop_exempt_used=used,
        ))

    # KFCC + 다양한 월저축 기간
    for m, period in [(100_000, 6), (300_000, 12), (500_000, 24), (1_000_000, 36)]:
        result.append(case(
            f"J{len(result)+1:02d}_KFCC_월저축{m//10000:,}만_기간{period}개월",
            capital=0, monthly_saving=m, period_months=period,
            main_bank_code=KFCC_CODES[2],
        ))

    # 균형형 조건 일부만 거부
    for mc, ai, at, suffix in [
        (False, True,  True,  "마케팅거부만"),
        (True,  False, True,  "앱불가만"),
        (True,  True,  False, "자동이체불가만"),
        (False, False, True,  "마케팅앱거부"),
        (True,  False, False, "앱자동이체거부"),
        (False, True,  False, "마케팅자동이체거부"),
    ]:
        result.append(case(
            f"J{len(result)+1:02d}_균형조건_{suffix}",
            capital=50_000_000, monthly_saving=0, period_months=12,
            main_bank_code=CU_CODES[6],
            marketing_consent=mc, app_install=ai, auto_transfer=at,
        ))

    # 목돈 + 월저축 + 예금자보호 초과 복합
    for cap, m in [(80_000_000, 300_000), (120_000_000, 500_000), (150_000_000, 1_000_000)]:
        result.append(case(
            f"J{len(result)+1:02d}_복합한도초과_목돈{cap//10000:,}만+월{m//10000:,}만",
            capital=cap, monthly_saving=m, period_months=12,
            main_bank_code=CU_CODES[7],
        ))

    # 2개월, 3개월 등 중간 기간
    for period in [2, 4, 9, 18, 30, 48]:
        result.append(case(
            f"J{len(result)+1:02d}_비표준기간_{period}개월",
            capital=30_000_000, monthly_saving=0, period_months=period,
            main_bank_code=CU_CODES[8],
        ))

    # CU main_bank + 고소득 + 조합원가입 (저율과세 미적용이지만 조합원)
    result.append(case(
        f"J{len(result)+1:02d}_CU_고소득_조합원가입",
        capital=50_000_000, monthly_saving=500_000, period_months=12,
        main_bank_code=CU_CODES[9],
        accepts_membership=True, coop_tax_eligible=False,
    ))

    # KFCC main_bank + 조합원 모름 + 저율과세 모름
    result.append(case(
        f"J{len(result)+1:02d}_KFCC_세금조건모름",
        capital=50_000_000, monthly_saving=0, period_months=12,
        main_bank_code=KFCC_CODES[9],
        accepts_membership=None, coop_tax_eligible=None,
    ))

    return result  # 49건


def group_k() -> list[dict]:
    """K. 은행·저축은행 주거래 (40건) — 단순형 반영 여부 검증용"""
    result = []

    # K01-K05: 국민은행 주거래
    for cap, m, period, suffix in [
        (10_000_000, 0, 12, "목돈1,000만_12개월"),
        (50_000_000, 0, 12, "목돈5,000만_12개월"),
        (0, 500_000, 12, "월저축50만_12개월"),
        (30_000_000, 300_000, 12, "목돈3,000만+월30만_12개월"),
        (100_000_000, 0, 24, "목돈10,000만_24개월"),
    ]:
        result.append(case(
            f"K{len(result)+1:02d}_국민_{suffix}",
            capital=cap, monthly_saving=m, period_months=period,
            main_bank_code=BANK_CODES["국민"],
        ))

    # K06-K10: 신한은행 주거래
    for cap, m, period, suffix in [
        (10_000_000, 0, 6,  "목돈1,000만_6개월"),
        (50_000_000, 0, 12, "목돈5,000만_12개월"),
        (0, 300_000, 24, "월저축30만_24개월"),
        (20_000_000, 200_000, 12, "목돈2,000만+월20만_12개월"),
        (150_000_000, 0, 36, "목돈15,000만_36개월"),
    ]:
        result.append(case(
            f"K{len(result)+1:02d}_신한_{suffix}",
            capital=cap, monthly_saving=m, period_months=period,
            main_bank_code=BANK_CODES["신한"],
        ))

    # K11-K15: 하나은행 주거래
    for cap, m, period, suffix in [
        (5_000_000, 0, 6,   "목돈500만_6개월"),
        (30_000_000, 0, 12, "목돈3,000만_12개월"),
        (0, 1_000_000, 12, "월저축100만_12개월"),
        (50_000_000, 500_000, 12, "목돈5,000만+월50만_12개월"),
        (200_000_000, 0, 12, "목돈20,000만_12개월"),
    ]:
        result.append(case(
            f"K{len(result)+1:02d}_하나_{suffix}",
            capital=cap, monthly_saving=m, period_months=period,
            main_bank_code=BANK_CODES["하나"],
        ))

    # K16-K20: 인터넷 은행 (카카오/토스)
    for bank, cap, m, period, suffix in [
        ("카카오", 10_000_000, 0, 12, "목돈1,000만_12개월"),
        ("카카오", 50_000_000, 0, 12, "목돈5,000만_12개월"),
        ("토스",   10_000_000, 0, 6,  "목돈1,000만_6개월"),
        ("토스",   30_000_000, 0, 12, "목돈3,000만_12개월"),
        ("토스",   0, 500_000, 24,    "월저축50만_24개월"),
    ]:
        result.append(case(
            f"K{len(result)+1:02d}_{bank}_{suffix}",
            capital=cap, monthly_saving=m, period_months=period,
            main_bank_code=BANK_CODES[bank],
        ))

    # K21-K25: 기타 은행 (우리/농협/기업/수협/경남)
    for bank, cap, m, period, suffix in [
        ("우리", 50_000_000, 0, 12, "목돈5,000만_12개월"),
        ("농협", 30_000_000, 0, 12, "목돈3,000만_12개월"),
        ("기업", 50_000_000, 300_000, 12, "목돈5,000만+월30만_12개월"),
        ("수협", 10_000_000, 0, 6,  "목돈1,000만_6개월"),
        ("경남", 50_000_000, 0, 12, "목돈5,000만_12개월"),
    ]:
        result.append(case(
            f"K{len(result)+1:02d}_{bank}_{suffix}",
            capital=cap, monthly_saving=m, period_months=period,
            main_bank_code=BANK_CODES[bank],
        ))

    # K26-K30: 저축은행 주거래
    for sb, cap, m, period, suffix in [
        ("SBI",    10_000_000, 0, 12, "목돈1,000만_12개월"),
        ("OK",     30_000_000, 0, 12, "목돈3,000만_12개월"),
        ("웰컴",   50_000_000, 0, 12, "목돈5,000만_12개월"),
        ("한국투자", 0, 500_000, 24,  "월저축50만_24개월"),
        ("KB저축", 10_000_000, 500_000, 12, "목돈1,000만+월50만_12개월"),
    ]:
        result.append(case(
            f"K{len(result)+1:02d}_{sb}저축_{suffix}",
            capital=cap, monthly_saving=m, period_months=period,
            main_bank_code=SB_CODES[sb],
        ))

    # K31-K35: 우대조건 조합 (국민/신한/하나 주거래)
    for bank, mc, ai, at, suffix in [
        ("국민", False, True,  True,  "마케팅거부"),
        ("신한", True,  False, True,  "앱불가"),
        ("하나", True,  True,  True,  "모든조건충족"),
        ("카카오", None, None, None,  "모든조건모름"),
        ("토스", True,  True,  False, "자동이체불가"),
    ]:
        result.append(case(
            f"K{len(result)+1:02d}_{bank}_{suffix}_목돈5,000만_12개월",
            capital=50_000_000, monthly_saving=0, period_months=12,
            main_bank_code=BANK_CODES[bank],
            marketing_consent=mc, app_install=ai, auto_transfer=at,
        ))

    # K36-K40: 복합 시나리오
    for bank_or_sb, code, cap, m, period, suffix in [
        ("국민", BANK_CODES["국민"],   100_000_000, 1_000_000, 12, "대형자산_목돈10,000만+월100만"),
        ("신한", BANK_CODES["신한"],     1_000_000, 0,          3, "소액_목돈100만_3개월"),
        ("하나", BANK_CODES["하나"],           0,  300_000,    36, "장기_월저축30만_36개월"),
        ("농협", BANK_CODES["농협"],    50_000_000, 1_000_000, 24, "복합_목돈5,000만+월100만_24개월"),
        ("SBI저축", SB_CODES["SBI"],    5_000_000,  0,          6, "저액_목돈500만_6개월"),
    ]:
        result.append(case(
            f"K{len(result)+1:02d}_{bank_or_sb}_{suffix}",
            capital=cap, monthly_saving=m, period_months=period,
            main_bank_code=code,
        ))

    return result  # 40건


# ---------------------------------------------------------------------------
# 생성
# ---------------------------------------------------------------------------
def main() -> None:
    all_cases = (
        group_a() +  # 32
        group_b() +  # 20
        group_c() +  # 48
        group_d() +  # 27
        group_e() +  # 24
        group_f() +  # 20
        group_g() +  # 30
        group_h() +  # 30
        group_i() +  # 20
        group_j() +  # 49
        group_k()    # 40
    )

    assert len(all_cases) == 340, f"케이스 수 오류: {len(all_cases)}건"

    OUT_PATH.write_text(
        json.dumps(all_cases, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"생성 완료: {len(all_cases)}건 → {OUT_PATH}")

    # 그룹별 건수 확인
    group_counts = {}
    for c in all_cases:
        g = c["label"][0]
        group_counts[g] = group_counts.get(g, 0) + 1
    for g, cnt in sorted(group_counts.items()):
        print(f"  그룹 {g}: {cnt}건")


if __name__ == "__main__":
    main()
