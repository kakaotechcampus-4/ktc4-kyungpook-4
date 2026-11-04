"""사용자 프로필 API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.institution import Institution
from app.models.profile import UserProfile, UserProfileBank, UserProfileSocial, UserProfileTaxExempt
from app.models.user import AppUser
from app.schemas.profile import (
    EtcAnswerResultOut,
    EtcAnswersIn,
    EtcAnswersOut,
    EtcQuestionOut,
    EtcQuestionsOut,
    ProfileCreate,
    ProfileOut,
)
from app.services import chatbot
from app.services.onboarding import interpret

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("", response_model=ProfileOut, status_code=201, summary="입력값 스냅샷 생성 (STEP1~3)")
async def create_profile(
    body: ProfileCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProfileOut:
    if body.lump_sum == 0 and body.monthly_saving == 0:
        raise HTTPException(status_code=422, detail="목돈 또는 월 저축액 중 하나는 0보다 커야 합니다")

    parsed = interpret(body)
    # 은행 코드는 우리가 정한 매핑이라 요청 오류가 아니다. DB 에 없는 기관(시드만 넣은 개발 DB 등)은 빼고 저장한다
    requested_codes = set(parsed.held_bank_codes) | ({parsed.main_bank_code} if parsed.main_bank_code else set())
    found: set[str] = set()
    if requested_codes:
        found = set(
            (
                await session.execute(
                    select(Institution.institution_code).where(Institution.institution_code.in_(requested_codes))
                )
            ).scalars()
        )
    held_bank_codes = [code for code in parsed.held_bank_codes if code in found]
    main_bank_code = parsed.main_bank_code if parsed.main_bank_code in found else None

    user_id = body.user_id
    if user_id is None:
        # 로그인 연동 전까지는 요청마다 익명 사용자를 만든다
        user = AppUser(nickname="guest")
        session.add(user)
        await session.flush()
        user_id = user.user_id

    profile = UserProfile(
        user_id=user_id,
        capital=body.lump_sum,
        monthly_saving=body.monthly_saving,
        period_months=body.period_months,
        main_bank_code=main_bank_code,
        birth_date=parsed.birth_date,
        salary_transfer=parsed.salary_transfer,
        auto_transfer=parsed.auto_transfer,
        savings_auto_transfer=parsed.savings_auto_transfer,
        pension_transfer=parsed.pension_transfer,
        coop_insurance=parsed.coop_insurance,
        monthly_card_usage=parsed.monthly_card_usage,
        marketing_consent=parsed.marketing_consent is True,  # 컬럼이 NOT NULL 이라 모름은 미동의로 저장
        app_install=parsed.app_install,
        accepts_membership=parsed.accepts_membership,
        coop_tax_eligible=parsed.coop_tax_eligible,
        coop_exempt_used=parsed.coop_exempt_used,
        answers=parsed.answers,
        banks=[UserProfileBank(institution_code=code) for code in held_bank_codes],
        tax_exempts=[UserProfileTaxExempt(category=c) for c in parsed.tax_exempt_categories],
        social_cares=[UserProfileSocial(category=c) for c in parsed.social_categories],
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return ProfileOut(
        profile_id=profile.profile_id,
        user_id=profile.user_id,
        capital=profile.capital,
        monthly_saving=profile.monthly_saving,
        period_months=profile.period_months,
        main_bank_code=profile.main_bank_code,
        held_bank_codes=held_bank_codes,
        accepts_membership=profile.accepts_membership,
        coop_tax_eligible=profile.coop_tax_eligible,
        coop_exempt_used=profile.coop_exempt_used,
        created_at=profile.created_at,
    )


async def _get_profile(session: AsyncSession, profile_id: int) -> UserProfile:
    profile = await session.get(UserProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다")
    return profile


@router.post(
    "/{profile_id}/etc-questions",
    response_model=EtcQuestionsOut,
    summary="챗봇 질문 받기 - 추천 결과 상품의 '기타' 우대조건 (STEP3)",
)
async def create_etc_questions(
    profile_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EtcQuestionsOut:
    """지금 추천 결과(4개 티어)에 들어간 상품의 '기타' 우대조건 중 아직 답하지 않은 것을 질문으로 만든다.
    질문 문장을 AI 로 만들어 몇 초 걸릴 수 있다. 이미 답한 조건은 다시 묻지 않는다."""
    profile = await _get_profile(session, profile_id)
    questions = await chatbot.build_questions(session, profile)
    return EtcQuestionsOut(
        questions=[
            EtcQuestionOut(question=q.question, evidence_text=q.evidence_text, condition_ids=q.condition_ids)
            for q in questions
        ]
    )


@router.post(
    "/{profile_id}/etc-answers",
    response_model=EtcAnswersOut,
    summary="챗봇 답 보내기 - 해석해서 저장 (STEP3)",
)
async def save_etc_answers(
    profile_id: int,
    body: EtcAnswersIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EtcAnswersOut:
    """답을 충족/미충족으로 해석해 저장한다 (애매하면 미충족). 같은 조건에 다시 답하면 덮어쓴다.
    저장 후 POST /portfolios/recommend 를 다시 부르면 답이 반영된 결과가 나온다."""
    profile = await _get_profile(session, profile_id)
    answers = [chatbot.EtcAnswer(a.condition_ids, a.question, a.answer) for a in body.answers]
    try:
        results = await chatbot.save_answers(session, profile, answers)
    except chatbot.UnknownConditionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return EtcAnswersOut(results=[EtcAnswerResultOut(condition_ids=r.condition_ids, met=r.met) for r in results])
