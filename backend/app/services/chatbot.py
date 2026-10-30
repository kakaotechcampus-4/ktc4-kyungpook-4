"""챗봇 - 추천 결과에 들어간 상품의 '기타' 우대조건을 사용자에게 묻고, 답을 저장한다.

[흐름]
  1) POST /portfolios/recommend        1차 추천 ('기타' 조건은 최대형에서만 달성 가정)
  2) build_questions()                 1차 결과 상품의 '기타' 조건으로 질문을 만든다 (AI 호출 A)
  3) save_answers()                    사용자 답을 해석해 저장한다 (AI 호출 B)
  4) POST /portfolios/recommend        다시 추천 = 최종. 저장된 답이 conditions.py 에서 반영된다
     (충족 -> 균형형부터 / 미충족(모름 포함) -> 어디서도 제외 / 답 없음 -> 최대형만)

[범위 - 2026-10-30 결정]
  - 묻는 상품: 단순·균형·최대·안정 4개 티어 결과에 들어간 상품. 단일형은 비교 기준선이라 뺀다.
  - 묻는 조건: '기타' 이면서 우대폭이 있고, 그 상품에 배분된 기간에 적용되는 조건.
    단 최고금리가 기본금리와 같은 옵션(우대금리가 붙을 여지가 없음)의 조건은 답이 결과를 바꾸지 못해 묻지 않는다.
    (새마을금고는 공시에 최고금리 구분이 없어 ERD 에서 최고금리 = 기본금리 -> 지금은 새마을금고 조건을 묻지 않게 된다)
  - 한 번만 묻는다: 이미 답한 조건은 다시 묻지 않는다. 다시 추천한 뒤 새로 들어온 상품의
    '기타' 조건은 묻지 않고 최대형에서만 가정한다 (계속 물으면 끝나지 않으므로).
  - 원문이 같은 조건은 질문 하나로 묶고(condition_ids), 답은 묶인 조건 전부에 저장한다.

질문 문장 생성과 답 해석은 AI 파트 모듈(ktc4_ai.condition_qa)이 한다. 애매하거나 실패하면 항상 '미충족'.
"""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from ktc4_ai.condition_qa import build_etc_questions, parse_answer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import ProductCondition, ProductOption
from app.models.profile import UserProfile, UserProfileExtra
from app.services.conditions import _applies_to_period
from app.services.portfolio import ETC_ANSWER_MET, ETC_ANSWER_NOT_MET, PortfolioPlan, build_tiers

ETC_TYPE = "기타"
# 답 해석에서 AI 를 동시에 부르는 수. 너무 많이 보내면 API 프록시가 거부할 수 있다
MAX_PARALLEL_PARSE = 5


@dataclass(frozen=True)
class EtcQuestion:
    question: str
    evidence_text: str  # 우대조건 원문
    condition_ids: list[str]  # 이 질문의 답을 저장할 조건들 (원문이 같은 조건 묶음)


@dataclass(frozen=True)
class EtcAnswer:
    condition_ids: list[str]
    question: str
    answer: str  # 사용자가 입력한 원문


@dataclass(frozen=True)
class EtcAnswerResult:
    condition_ids: list[str]
    met: bool  # 해석 결과. 애매하거나 실패하면 False


class UnknownConditionError(ValueError):
    """'기타' 조건이 아닌(또는 없는) condition_id 로 답을 저장하려 했다."""

    def __init__(self, condition_ids: list[str]) -> None:
        super().__init__(f"'기타' 우대조건이 아니거나 없는 condition_id: {condition_ids}")
        self.condition_ids = condition_ids


def recommended_options(plan: PortfolioPlan) -> dict[str, ProductOption]:
    """추천 결과(단일형 제외 4개 티어)에 들어간 상품 -> 그 상품에 배분된 옵션(기간·금리)."""
    options: dict[str, ProductOption] = {}
    for tier in plan.tiers.values():
        for alloc in (*tier.deposit_allocs, *tier.installment_allocs):
            options[alloc.product.product_id] = alloc.option
    return options


def select_question_targets(
    conditions: list[ProductCondition], options: dict[str, ProductOption], answered_ids: set[str]
) -> list[ProductCondition]:
    """물어볼 조건: '기타' + 우대폭 있음 + 아직 답하지 않음 + 배분된 옵션에서 결과를 바꿀 수 있음
    (그 기간에 적용되고, 최고금리가 기본금리보다 높아 우대금리가 붙을 여지가 있음)."""
    targets = []
    for c in conditions:
        option = options.get(c.product_id)
        if (
            option is not None
            and c.condition_type == ETC_TYPE
            and c.rate_bonus is not None
            and c.condition_id not in answered_ids
            and option.max_rate > option.base_rate
            and _applies_to_period(c, option.period_months)
        ):
            targets.append(c)
    return targets


def _to_ai_input(cond: ProductCondition) -> dict:
    """ktc4_ai.condition_qa 가 받는 형식 (ProductCondition 필드명 그대로)."""
    return {
        "condition_id": cond.condition_id,
        "condition_type": cond.condition_type,
        "rate_bonus": float(cond.rate_bonus) if cond.rate_bonus is not None else None,
        "evidence_text": cond.evidence_text,
    }


async def build_questions(session: AsyncSession, profile: UserProfile) -> list[EtcQuestion]:
    """지금 추천 결과에 들어간 상품의 '기타' 조건 중 아직 묻지 않은 것으로 질문을 만든다."""
    options = recommended_options(await build_tiers(session, profile))
    if not options:
        return []

    cond_stmt = select(ProductCondition).where(
        ProductCondition.product_id.in_(list(options)), ProductCondition.condition_type == ETC_TYPE
    )
    conditions = list((await session.execute(cond_stmt)).scalars())
    answered_stmt = select(UserProfileExtra.condition_id).where(UserProfileExtra.profile_id == profile.profile_id)
    answered = set((await session.execute(answered_stmt)).scalars())

    targets = select_question_targets(conditions, options, answered)
    if not targets:
        return []
    # 질문 문장 생성은 동기 함수(AI 호출, 내부에서 동시에 여러 개)라 이벤트 루프를 막지 않게 스레드로 돌린다
    groups = await asyncio.to_thread(build_etc_questions, [_to_ai_input(c) for c in targets])
    return [EtcQuestion(g["question"], g["evidence_text"], g["condition_ids"]) for g in groups]


async def _parse_all(raw_answers: list[str]) -> list[bool]:
    """답 해석(짧은 답은 AI 없이, 문장은 AI)을 동시에 MAX_PARALLEL_PARSE 개까지 돌린다."""
    semaphore = asyncio.Semaphore(MAX_PARALLEL_PARSE)

    async def one(raw: str) -> bool:
        async with semaphore:
            return await asyncio.to_thread(parse_answer, raw)

    return list(await asyncio.gather(*(one(raw) for raw in raw_answers)))


async def save_answers(session: AsyncSession, profile: UserProfile, answers: list[EtcAnswer]) -> list[EtcAnswerResult]:
    """답을 해석해 condition_ids 각각에 한 줄씩 저장한다. 이미 답한 조건이면 새 답으로 덮어쓴다."""
    all_ids = {cid for a in answers for cid in a.condition_ids}
    if not all_ids:
        return []
    found_stmt = select(ProductCondition.condition_id).where(
        ProductCondition.condition_id.in_(all_ids), ProductCondition.condition_type == ETC_TYPE
    )
    found = set((await session.execute(found_stmt)).scalars())
    if unknown := sorted(all_ids - found):
        raise UnknownConditionError(unknown)

    mets = await _parse_all([a.answer for a in answers])
    answered_at = datetime.now(UTC)
    rows: dict[str, dict] = {}  # condition_id -> 저장할 값. 같은 조건이 두 번 오면 뒤의 답을 쓴다
    for answer, met in zip(answers, mets, strict=True):
        for cid in answer.condition_ids:
            rows[cid] = {
                "profile_id": profile.profile_id,
                "condition_id": cid,
                "condition_type": ETC_TYPE,
                "question_text": answer.question,
                "answer_value": ETC_ANSWER_MET if met else ETC_ANSWER_NOT_MET,
                "raw_answer": answer.answer,
                "answered_at": answered_at,
            }

    stmt = insert(UserProfileExtra).values(list(rows.values()))
    stmt = stmt.on_conflict_do_update(
        constraint="uq_user_profile_extra_profile_id",
        set_={
            "question_text": stmt.excluded.question_text,
            "answer_value": stmt.excluded.answer_value,
            "raw_answer": stmt.excluded.raw_answer,
            "answered_at": stmt.excluded.answered_at,
        },
    )
    await session.execute(stmt)
    await session.commit()
    return [EtcAnswerResult(a.condition_ids, met) for a, met in zip(answers, mets, strict=True)]