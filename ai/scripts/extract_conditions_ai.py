"""
product_condition(우대조건)을 정규식이 아니라 실제 Claude Sonnet 5 AI 호출로 뽑는 스크립트.
(build_erd_tables.py는 이 스크립트가 만든 캐시 파일을 읽어서 최종 테이블을 만든다 - 2단계 구조)

지금 처리 대상(스코프 결정: 은행+저축은행+신협+새마을금고 "전체"):
- 은행 2개 파일(deposit_sample.json, saving_sample.json) - 우대조건 원문(spcl_cnd) 있음 -> AI로 뽑음
- 저축은행 2개 파일(deposit_savingsbank_sample.json, saving_savingsbank_sample.json)
  - 우대조건 원문(spcl_cnd) 있음 -> AI로 뽑음 (지난번엔 범위에서 뺐었는데 이번엔 포함)
- 신협(cu_rate_compare.jsonl): prefCondMemo에 우대조건 자유텍스트가 있음(단, 지점별로
  같은 문구가 반복되고 대부분 "①...: 0.0%p" 처럼 실제 값이 다 0인 빈 템플릿) -> 0이 아닌
  %p가 하나라도 있는 것만 골라서(gather_cu_targets) AI로 뽑음.
- 새마을금고(kfcc_rates.jsonl): 숫자 금리표만 있고 우대조건 자유텍스트가 없음 -> 대신
  중앙 공통상품 카탈로그 원문(kfcc_central_conditions_raw.jsonl)을 gather_kfcc_targets()로
  처리함(상품명 매칭되는 중앙 공통상품만 대상).

동작 순서:
1. 소스 파일들을 읽어서, base 상품(fin_co_no+fin_prdt_cd)별로 spcl_cnd 원문을 모은다.
2. 원문이 있는 상품마다 Claude Sonnet 5를 호출해서 구조화된 조건 리스트
   (설명 + %p + 적용 만기)로 뽑는다. (src/schemas/extraction.py의 ExtractionResult 그대로 재사용)
3. 이미 처리한 상품은 캐시 파일(output/ai_condition_cache.jsonl)에 남겨서, 중간에
   끊기거나 재실행해도 같은 상품을 또 API 호출하지 않는다(비용/시간 절약, 이어서 실행 가능).

[v3 변경사항] 285건 실제로 돌려서 MISMATCH 샘플을 까본 결과, AI가 뽑은 %p 값 자체는
맞았는데 "3~5개월"처럼 범위로 된 만기 조건을 "3개월 이상 전부"로 잘못 넓게 적용해서
생기는 오차가 있었음. max_term_months(상한)를 스키마/프롬프트에 추가해서 범위/미만
조건도 정확히 표현하도록 고침 - 이 스키마 변경은 기존에 이미 처리된 상품에도 영향을
주므로, 이번엔 --fresh로 전부 다시 뽑아야 함(실패한 것만 재시도하는 기존 방식으론
스키마가 바뀐 걸 반영 못함).

[v4 변경사항] v3까지 고치고도 남아있던 MISMATCH를 다시 까보니, "①②③ 중 하나만 인정"
같은 대체관계 조건을 무조건 다 더해버려서 생기는 오차였음. BE ERD에 원래 있었지만
한 번도 안 쓰던 exclusion_group 컬럼을 이번에 실제로 활용 - AI가 대체관계인 조건들에
같은 group_id를 붙이면, 검증/최종 테이블 둘 다 "그룹 안에서는 최댓값만, 그룹끼리는
합산"으로 계산하도록 바꿈. 이것도 스키마 변경이라 --fresh로 다시 뽑아야 반영됨.

[v5 변경사항] v4 이후 남은 MISMATCH를 다시 까보니 크게 두 가지 원인이 더 있었음:
1) 원문에 "최고우대금리:0.7%", "최대 0.1%p 가산" 처럼 개별 조건을 다 더해도 절대
   못 넘는 전체 상한이 명시돼 있는데, 이걸 안 쓰고 그냥 다 더해서 실제보다 크게
   계산되는 경우 -> ExtractionResult에 overall_max_bonus_rate(전체 상한) 필드를
   추가하고, compute_extracted_total에서 합계를 이 상한으로 min() 씌우도록 고침.
2) 신용점수/자녀수/걸음수/횟수 구간처럼 "①②③ 번호"가 아니라 그냥 나열된 숫자
   구간형 조건들에 group_id가 잘 안 붙는 경우가 있었음(프롬프트에 규칙은 있었지만
   번호 없이 나열된 구간엔 모델이 잘 안 따름) -> 프롬프트에 이런 패턴의 few-shot
   예시를 추가해서 그룹핑 안정성을 높임(단, LLM 특성상 100% 보장은 아님).
   참고: 고객 속성(신용점수/자녀수 등)에 따라 달라지는 조건은 애초에 이 만기별
   공시금리 비교 방식으로는 검증이 안 되는 게 정상 - 이런 건 그대로 저장해두고
   나중에 추천 서비스가 사용자에게 직접 물어보는 용도로 쓰면 됨(검증 실패가 아니라
   이 검증 방법의 태생적 한계).

[v6 변경사항] v5의 overall_max_bonus_rate를 실제 20건에 붙여보니, "최대 1.57%p"처럼
원문에 적힌 상한 헤드라인이 정작 그 아래 적힌 만기별 예외(예: "특판우대이율:
0.50%p(24개월 0.85%p)")까지는 반영 안 한 값이라, 그 특정 만기에서는 진짜 합계가
상한보다 더 큰 게 맞는 경우가 있었음. 상한을 무조건 min()으로 강제하면 이런 경우
오히려 맞는 계산을 틀리게 만들어버림 - verify_against_options에서 "상한 적용
전/후 합계 중 하나라도 공시값과 맞으면 인정"으로 완화해서 이 역효과를 없앰.
(그 외 남은 MISMATCH는 원문 자체에 정보가 없거나(만기별로 늘어나는 별도
이벤트 우대가 spcl_cnd 밖에 있음) group_id 판단이 갈리는 경계 케이스라, 이 이상은
프롬프트를 더 조여도 반대 방향 오류가 새로 생길 위험이 커서 - v5 문서에 적은 대로
confidence_badge=LOW로 넘기고 계속 파고들지 않기로 함.)

[v7 변경사항] product_condition의 condition_type(우대조건 종류: 급여이체/자동이체/
신규고객 등)이 그동안 AI가 아니라 build_erd_tables.py의 단순 키워드 매칭
(classify_condition_type)으로 채워지고 있었음 - 이건 AI 도입 전 정규식 시절 로직이
그대로 남아있던 것. 이제 이것도 AI가 description을 보고 직접 분류하도록 바꿈
(PreferentialCondition.condition_type 필드 추가, 프롬프트에 카테고리 목록 명시).
스키마 변경이라 --fresh로 다시 뽑아야 반영됨.

[v8 변경사항] v7 스키마로 285건 전체 재실행 후 7건이 계속 실패("ExtractionResult로
해석 안 됨")했음. 까보니 전부 같은 원인: 원문에 "금리우대 코드를 입력하는 경우"처럼
외부 코드/쿠폰에 따라 달라지거나, "임신 또는 출산", "미취학 자녀수에 따른 차등"처럼
고객 속성에 따라 달라지거나, 전체 범위(0.1~0.5%)만 있고 개별 항목별 %가 안 쪼개진
경우처럼 그 조건 하나만의 구체적 %p가 원문에 없어서, AI가 bonus_rate를 null로
줬는데 스키마(필수 float)가 이를 거부해서 파싱 자체가 실패로 떨어졌던 것.
PreferentialCondition.bonus_rate를 Optional로 바꿔서 null도 저장되게 하고,
compute_extracted_total에서는 bonus_rate가 null인 조건을 0으로 취급(합계에서 제외)
하도록 고침 - 이런 조건도 description/condition_type은 그대로 저장되니, 정량적
검증에는 안 쓰이지만 나중에 챗봇/추천엔진이 "이 상품엔 이런 조건도 있다"는 걸
안내하는 용도로는 계속 활용 가능. 프롬프트에도 "모르면 지어내지 말고 null" 지시를
명시적으로 추가함. 스키마 변경이라 --fresh로 다시 뽑아야 반영됨.

[v9 변경사항] BE ERD의 product_condition.threshold_value/threshold_unit 컬럼이
처음 설계 때부터 있었는데, 지금까지 AI 추출 스키마에 대응 필드가 없어서 한 번도
채워지지 않고 항상 null로 저장되고 있었음(build_erd_tables.py에서 하드코딩).
그래서 "이 조건을 충족하려면 넘어야 하는 숫자 기준"(예: "급여이체 50만원 이상"의
50/만원)이 evidence_text 원문 안에만 텍스트로 남아있었음 - 나중에 사용자 입력값과
이 조건을 비교하는 실시간 매칭 로직을 짜는 사람이 매번 원문을 다시 정규식으로
파싱해야 하는 부담이 있었음. PreferentialCondition에 threshold_value(float)/
threshold_unit(str) 필드를 추가하고 프롬프트에 추출 규칙을 명시함 - 이제
build_erd_tables.py가 이 값을 그대로 product_condition에 채워넣음(별도 코드
수정 완료, ERD 테이블 구조 자체는 안 바뀜 - 원래 있던 빈 컬럼을 채우는 것뿐).
스키마 변경이라 --fresh로 다시 뽑아야 반영됨.

[v10 변경사항] 만기별 실제 공시 우대폭과 AI 추출 합계를 비교하던 수치 검증
(verify_against_options/compute_extracted_total/condition_applies, verification_status/
confidence_badge 필드)을 완전히 제거함. 이 파이프라인은 커뮤니티/블로그 등 비공식
소스를 긁어오는 게 아니라 금감원 공시(finlife)/신협/새마을금고 공식 데이터를 그대로
쓰기 때문에, 원문 자체의 신뢰도를 AI가 재검증할 필요가 낮다고 판단(2026-09-28 팀
결정). BE ERD에서도 product_condition의 verification_status/confidence_badge
컬럼을 이미 제거함(관련 커밋 aab0efc). AI 개입 범위(질문 생성/자유텍스트 답변
해석)의 신뢰 경계는 별도로 ai/scripts/condition_qa.py에 정리함.
실행:
  python scripts\\extract_conditions_ai.py --limit 20 --fresh   (테스트로 20건만 새로)
  python scripts\\extract_conditions_ai.py --fresh              (전체를 새 스키마로 재실행)
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from src.schemas.extraction import ExtractionResult

from openai import OpenAI

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
CACHE_PATH = Path(__file__).resolve().parent.parent / "output" / "ai_condition_cache.jsonl"
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

EMPTY_SPCL_CND = {"없음", "해당사항 없음", "해당없음", "우대금리 없음", ""}

# (파일명, institution_type, evidence_url) - spcl_cnd(자유텍스트 우대조건) + optionList(intr_rate/intr_rate2)
# 구조를 가진 소스만 여기 등록. 신협/새마을금고는 지금 가진 파일에 이 구조가 없어서 비어있음 -
# 우대조건 원문 파일을 찾으면 이 리스트에 추가하면 그대로 처리됨.
FINLIFE_LIKE_SOURCES = [
    ("deposit_sample.json", "은행", "https://finlife.fss.or.kr"),
    ("saving_sample.json", "은행", "https://finlife.fss.or.kr"),
    ("deposit_savingsbank_sample.json", "저축은행", "https://finlife.fss.or.kr"),
    ("saving_savingsbank_sample.json", "저축은행", "https://finlife.fss.or.kr"),
]

SYSTEM_PROMPT = (
    "너는 예적금 상품의 우대조건 원문을 분석하는 어시스턴트야. "
    "주어진 원문에서 개별 우대조건과 그 조건이 주는 우대금리(%p)를 "
    "빠짐없이, 원문에 없는 내용은 지어내지 말고 추출해.\n\n"
    "만기(개월) 적용 범위는 다음 규칙으로 채워:\n"
    "- '정확히 X개월'에만 적용되면: applicable_term_months=X (min/max는 비움)\n"
    "- 'X개월 이상'처럼 하한만 있으면: min_term_months=X\n"
    "- 'X개월 이하/까지'처럼 상한만 있으면: max_term_months=X\n"
    "- 'X~Y개월'처럼 범위면: min_term_months=X, max_term_months=Y\n"
    "- 'X개월 미만'이면: max_term_months=X-1 (예: '12개월 미만' -> max_term_months=11)\n"
    "- 'X개월 초과'면: min_term_months=X+1\n"
    "- 만기 제한이 아예 없으면(모든 만기에 적용) 셋 다 비움(null)\n\n"
    "group_id(중요): 여러 조건 중 하나만 인정되고 서로 더해지지 않는(대체 관계인) "
    "조건들에는 반드시 같은 group_id 문자열을 붙여줘. 아래가 대표적인 경우들이야:\n"
    "1) 같은 항목을 금액/실적 구간별로 나눠서 설명한 경우 (예: '300만원 이상 0.1%, "
    "500만원 이상 0.2%' -> 이 둘은 같은 group_id. 실제로는 구간 중 하나만 해당되니까)\n"
    "2) 원문 맨 위에 '최고/최대 X%p' 같은 전체 상한이 명시돼 있고, 그 아래 나열된 "
    "①②③... 조건들이 그 상한 안에서 아무거나 하나만 인정되는 구조인 경우 "
    "-> 나열된 조건 전부에 같은 group_id를 붙여줘\n"
    "3) ①②③ 번호가 없어도, 신용점수/자녀 수/가구원 수/걸음 수/이용 실적 금액처럼 "
    "'하나의 기준을 놓고 값이 커질수록 우대금리가 올라가는 여러 구간'을 나열한 경우는 "
    "번호가 있든 없든 전부 같은 group_id로 묶어줘. 예를 들어 원문이\n"
    "  '신용점수 850점 이하~650점 초과 1.0%p / 650점 이하~350점 초과 2.0%p / "
    "350점 이하~1점 이상 3.0%p'\n"
    "  '연간 걸음수 1백만보 이상 1.0%p / 2백만보 이상 2.0%p / 3백만보 이상 3.0%p'\n"
    "  '자녀 수 2명 우대이율 2.0%, 자녀 수 3명 이상 우대이율 3.0%'\n"
    "라면, 이건 모두 '하나의 기준(신용점수/걸음수/자녀수)에 대한 구간별 조건'이므로 "
    "각 구간에 같은 group_id(예: 'g_credit_score', 'g_steps', 'g_children')를 붙여야 해 "
    "(고객은 실제로 이 중 자신이 해당하는 구간 하나만 받으니까, 절대 다 더하면 안 돼).\n"
    "대체 관계가 아니라 각자 따로 더해지는(독립적인) 조건이면 group_id는 비워(null). "
    "그룹 이름은 그 그룹 안에서만 겹치지 않으면 되고, 자유롭게 지어도 돼.\n\n"
    "overall_max_bonus_rate(중요): 원문에 '최고우대금리:0.7%', '최대 0.1%p 가산 "
    "적용'처럼, 아래 나열된 개별 조건들을 각자 다 채워도 절대 넘을 수 없는 전체 "
    "상한이 명시돼 있으면 그 값을 여기에 채워(%p 단위, 예: 0.7). 이런 전체 상한 "
    "문구가 원문에 아예 없으면 null로 비워둬. 이건 개별 조건(conditions 배열의 "
    "각 항목)이 아니라 응답 전체에서 딱 한 번만 채우는 값이야.\n\n"
    "condition_type(중요): 각 조건이 어떤 종류인지, 아래 카테고리 중 하나로 반드시 "
    "분류해서 채워(정확히 이 문자열 그대로 써야 해):\n"
    "  '급여이체', '자동이체', '신규고객', '카드실적', '마케팅동의', '공과금이체', "
    "'연금수령', '비대면가입', '공제가입', '연령조건', '기타'\n"
    "- '공제가입': 신협공제 등 공제 상품 가입 실적 조건\n"
    "- '연령조건': 가입 연령 기준 충족 조건 (청년/어린이/시니어 등 나이 관련)\n"
    "위 10개 중 어디에도 명확히 해당 안 되면 '기타'를 써. description의 표면적인 "
    "단어가 아니라 그 조건의 실제 의미로 판단해(예: '급여통장 실적'은 겉보기엔 "
    "'통장'이지만 실제로는 '급여이체' 카테고리).\n\n"
    "bonus_rate(중요): 그 조건 하나에 대한 구체적인 %p 값이 원문에 명확히 있을 "
    "때만 채워. 다음처럼 원문만 봐서는 구체적인 값을 알 수 없는 경우엔 절대 "
    "숫자를 지어내지 말고 bonus_rate를 null로 둬:\n"
    "- '금리우대 코드를 입력하는 경우', '금리쿠폰을 입력시'처럼 외부 코드/쿠폰 "
    "체계에 따라 달라지고 원문에 그 자체의 %가 안 적혀 있는 경우\n"
    "- '임신 또는 출산', '미취학 자녀수에 따른 차등 적용', '한부모가족 지원 "
    "대상자'처럼 고객 속성에 따라 달라지는데 그 속성별 %가 원문에 안 적혀 "
    "있는 경우\n"
    "- 여러 항목이 나열돼 있는데 전체 범위(예: '0.1%~0.5%')만 있고 그 항목 "
    "하나하나에 대한 %가 원문에 따로 안 쪼개져 있는 경우\n"
    "이런 조건도 description과 condition_type은 그대로 채워서 빠뜨리지 마 - "
    "%p만 모르는 것뿐이니까.\n\n"
    "threshold_value / threshold_unit(중요): 그 조건을 충족하려면 넘어야 하는 "
    "숫자 기준이 원문에 있으면 뽑아줘. 예를 들어 '급여이체 50만원 이상'이면 "
    "threshold_value=50, threshold_unit='만원'. '월 5회 이상 이용'이면 "
    "threshold_value=5, threshold_unit='회'. '카드 실적 30만원 이상'이면 "
    "threshold_value=30, threshold_unit='만원'. 단위는 원문에 쓰인 표현을 그대로 "
    "써(예: '만원', '원', '회', '건', '명', '점', '보'). 숫자 기준 자체가 없는 "
    "조건(예: '신규고객', '마케팅 동의', '비대면 가입')이면 둘 다 null로 둬. "
    "여러 구간이 나열된 group_id 조건(예: '300만원 이상 0.1%, 500만원 이상 "
    "0.2%')은 각 구간 조건마다 그 구간 자신의 기준값을 따로 채워(첫 조건엔 "
    "threshold_value=300, 둘째 조건엔 threshold_value=500).\n\n"
    "반드시 아래 JSON 형식으로만 응답해. 코드블록(```) 없이, 설명 문장 없이, "
    "순수 JSON 객체 하나만 출력해:\n"
    '{"overall_max_bonus_rate": null, "conditions": [{"description": "조건 설명", '
    '"bonus_rate": 0.2, "condition_type": "기타", "applicable_term_months": null, '
    '"min_term_months": null, "max_term_months": null, "group_id": null, '
    '"threshold_value": null, "threshold_unit": null}]}'
)

CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_code_fence(text: str) -> str:
    return CODE_FENCE_RE.sub("", text.strip()).strip()


def _find_valid_result(node, depth=0):
    """모델이 응답을 이중으로 감싸는 경우(예: {"conditions": "{...}"} 처럼 conditions 값
    자체가 다시 JSON 문자열인 경우)까지 포함해서, 실제로 ExtractionResult로 검증되는
    딕셔너리를 재귀적으로 찾는다. (이 저장소에 이미 있던 test_extraction_verify.py의
    _find_valid와 같은 방식 - 이 API가 가끔 이렇게 이중으로 감싸서 응답하는 걸 확인해서 적용)"""
    if depth > 5:
        return None
    if isinstance(node, dict):
        try:
            return ExtractionResult(**node)
        except Exception:
            pass
        for value in node.values():
            candidate = value
            if isinstance(candidate, str):
                try:
                    candidate = json.loads(candidate)
                except Exception:
                    continue
            result = _find_valid_result(candidate, depth + 1)
            if result:
                return result
    return None



def load_cache():
    # [수정] 실패(error 있음)했던 건 "이미 처리됨"으로 치지 않는다 - 그래야 파싱 버그를
    # 고친 다음 다시 실행했을 때 실패했던 9건도 자동으로 재시도된다. (성공한 것만 캐시로
    # 인정 -> API 비용/시간 절약은 그대로 유지되면서, 실패 건은 계속 재시도됨)
    cache = {}
    if CACHE_PATH.exists():
        with CACHE_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if row.get("error"):
                    cache.pop(row["key"], None)
                    continue
                cache[row["key"]] = row
    return cache


def append_cache(row):
    with CACHE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")



def call_ai(client, spcl_cnd_text, retries=3):
    # [수정] 처음엔 client.beta.chat.completions.parse(response_format=ExtractionResult)로
    # 짜봤는데, 실제로 20건 테스트해보니 9건이 "conditions가 배열이 아니라 문자열"이라는
    # 검증 에러로 실패했음 - 이 API(엘리스 ML API 경유 Claude Sonnet 5)가 가끔 결과를
    # {"conditions": "{...json 문자열...}"} 처럼 이중으로 감싸서 주기 때문.
    # 그래서 순수 텍스트 응답을 받아서 직접 파싱 + 이중으로 감싸진 경우까지 풀어주는
    # _find_valid_result로 처리하도록 바꿈(이 저장소에 이미 있던 test_extraction_verify.py의
    # _find_valid 방식과 동일).
    last_raw = None
    for attempt in range(1, retries + 1):
        try:
            res = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": spcl_cnd_text},
                ],
            )
            content = res.choices[0].message.content
            last_raw = content
            node = json.loads(_strip_code_fence(content))
            parsed = _find_valid_result(node)
            if parsed is None:
                raise ValueError(f"ExtractionResult로 해석 안 됨. 원문 응답: {content[:300]}")
            return [c.model_dump() for c in parsed.conditions], parsed.overall_max_bonus_rate, None
        except Exception as e:
            if attempt == retries:
                msg = str(e)
                if last_raw:
                    msg += f" | 마지막 원문 응답: {last_raw[:300]}"
                return None, None, msg
            time.sleep(2 ** attempt)
    return None, None, "알 수 없는 오류"


def gather_targets():
    targets = []
    for filename, institution_type, evidence_url in FINLIFE_LIKE_SOURCES:
        path = FIXTURES / filename
        if not path.exists():
            print(f"[{filename}] 파일 없음 - 스킵")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        result = data.get("result", data)
        base_list = result.get("baseList") or []

        for base in base_list:
            spcl_cnd = (base.get("spcl_cnd") or "").strip()
            if spcl_cnd in EMPTY_SPCL_CND:
                continue
            fin_co_no = base.get("fin_co_no")
            fin_prdt_cd = base.get("fin_prdt_cd")
            key = f"{filename}:{fin_co_no}:{fin_prdt_cd}"
            targets.append({
                "key": key, "filename": filename, "institution_type": institution_type,
                "evidence_url": evidence_url, "fin_co_no": fin_co_no, "fin_prdt_cd": fin_prdt_cd,
                "spcl_cnd": spcl_cnd,
            })
    return targets


CU_JSONL_PATH = FIXTURES / "cu_rate_compare.jsonl"
CU_EMPTY_MEMO = {"없음", "null", ""}
NONZERO_RATE_RE = re.compile(r"[1-9]\d*\.?\d*%p|0\.[1-9]\d*%p")


def gather_cu_targets():
    """신협(cu_rate_compare.jsonl)의 prefCondMemo를 AI로 보낼 대상으로 모은다.
    지점마다 같은 문구가 반복되고 대부분 실제 값이 맨 0.0%p로 채워진 빈 템플릿이라,
    0이 아닌 %p가 하나라도 있는 것만 골라서 보낸다. 같은 상품(cuIngno+stockCode+tretYn)이
    지점/만기 개수만큼 같은 문구로 반복되므로 상품 단위로 중복 제거해서 한 번만 호출한다
    (비용 절약)."""
    targets = []
    seen = set()
    if not CU_JSONL_PATH.exists():
        print(f"[{CU_JSONL_PATH.name}] 파일 없음 - 스킵")
        return targets
    with CU_JSONL_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            memo = (rec.get("prefCondMemo") or "").strip()
            if memo in CU_EMPTY_MEMO or not NONZERO_RATE_RE.search(memo):
                continue
            cu_ingno = rec.get("cuIngno")
            stock_code = rec.get("stockCode")
            tret_yn = rec.get("tretYn")
            dedup_key = (cu_ingno, stock_code, tret_yn)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            fin_prdt_cd = f"{stock_code}_{tret_yn}"
            targets.append({
                "key": f"cu_rate_compare.jsonl:{cu_ingno}:{fin_prdt_cd}",
                "filename": "cu_rate_compare.jsonl",
                "institution_type": "신협",
                "evidence_url": rec.get("stockUrl") or "",
                "fin_co_no": cu_ingno,
                "fin_prdt_cd": fin_prdt_cd,
                "spcl_cnd": memo,
            })
    return targets


KFCC_FIXTURE = FIXTURES / "kfcc_central_conditions_raw.jsonl"


def gather_kfcc_targets():
    # 새마을금고 중앙 카탈로그 원문(fetch_kfcc_central_conditions.py가 만든 raw fixture)을
    # 읽어서 gather_targets()와 동일한 shape의 target 딕셔너리로 변환한다.
    targets = []
    if not KFCC_FIXTURE.exists():
        print(f"[{KFCC_FIXTURE.name}] 파일 없음 - 스킵")
        return targets

    with KFCC_FIXTURE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            spcl_cnd = (row.get("spcl_cnd_raw") or "").strip()
            if not spcl_cnd:
                continue
            goods_file = row.get("goods_file", "")
            product_name = row.get("product_name", "")
            targets.append({
                "key": f"kfcc_central:{goods_file}",
                "filename": "kfcc_central_conditions_raw.jsonl",
                "institution_type": "새마을금고",
                "evidence_url": row.get("source_url", ""),
                "fin_co_no": None,
                "fin_prdt_cd": product_name,
                "spcl_cnd": spcl_cnd,
            })
    return targets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="테스트용: 이 건수만 처리하고 멈춤")
    ap.add_argument("--sleep", type=float, default=0.3, help="API 호출 사이 대기 시간(초)")
    ap.add_argument("--fresh", action="store_true",
                     help="스키마/프롬프트를 바꾼 뒤 전부 다시 뽑고 싶을 때: 기존 캐시를 "
                          "'이미 처리됨'으로 치지 않고 전부 다시 호출한다(파일은 안 지움, "
                          "새 결과가 뒤에 이어붙고 그게 최종본으로 읽힘)")
    args = ap.parse_args()

    if not OPENAI_API_KEY or not OPENAI_BASE_URL:
        print("[!] OPENAI_API_KEY / OPENAI_BASE_URL이 .env에 설정 안 돼 있음 - 진행 불가")
        return

    client = OpenAI(api_key=OPENAI_API_KEY, base_url=f"{OPENAI_BASE_URL}/v1")
    cache = {} if args.fresh else load_cache()

    targets = gather_targets() + gather_cu_targets() + gather_kfcc_targets()
    if args.limit:
        targets = targets[: args.limit]
    print(f"처리 대상: {len(targets)}건 (이미 캐시에 있는 것 포함, 모델: {OPENAI_MODEL})\n")

    n_called = 0
    n_cached_reused = 0
    n_changed = 0
    n_failed = 0
    try:
        for t in targets:
            key = t["key"]
            cached_row = cache.get(key)
            # 캐시에 key가 있어도 그때 저장된 spcl_cnd(원문)와 지금 값이 다르면
            # "재추출 필요"로 본다 - 은행/조합이 우대조건 문구를 바꿨거나 데이터가
            # 갱신된 경우를 자동으로 잡기 위함. 이러면 --fresh(전체 재추출) 없이
            # fetch_*.py로 데이터를 새로 받아올 때마다 이 스크립트를 그냥 돌리기만
            # 해도 신규/변경 상품이 자동으로 반영된다. --fresh는 이제 카테고리
            # 자체를 새로 추가할 때 전용으로 쓰면 된다.
            if cached_row is not None and cached_row.get("spcl_cnd") == t["spcl_cnd"]:
                n_cached_reused += 1
            else:
                if cached_row is not None:
                    n_changed += 1
                conditions, overall_cap, error = call_ai(client, t["spcl_cnd"])
                n_called += 1
                if error:
                    n_failed += 1
                    conditions = []
                row = {
                    "key": key, "filename": t["filename"], "institution_type": t["institution_type"],
                    "evidence_url": t["evidence_url"], "fin_co_no": t["fin_co_no"],
                    "fin_prdt_cd": t["fin_prdt_cd"], "spcl_cnd": t["spcl_cnd"],
                    "conditions": conditions, "overall_max_bonus_rate": overall_cap,
                    "error": error,
                }
                append_cache(row)
                cache[key] = row
                time.sleep(args.sleep)

            done = n_called + n_cached_reused
            if done % 20 == 0:
                print(f"...진행 {done}/{len(targets)}건 (신규 호출 {n_called}, 캐시 재사용 {n_cached_reused}, 실패 {n_failed})")
    except KeyboardInterrupt:
        print("\n[중단됨] 지금까지 처리한 건 캐시에 저장돼 있어서, 다시 실행하면 이어서 진행됩니다.")

    print()
    print("=== 완료 ===")
    print(f"전체 대상: {len(targets)}건")
    print(f"신규 API 호출: {n_called}건(그중 원문 변경 감지: {n_changed}건) / 캐시 재사용: {n_cached_reused}건 / 실패: {n_failed}건")
    print(f"캐시 파일: {CACHE_PATH}")


if __name__ == "__main__":
    main()