"""사용자 프로필 API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.institution import Institution
from app.models.profile import UserProfile, UserProfileBank, UserProfileSocial, UserProfileTaxExempt
from app.models.user import AppUser
from app.schemas.profile import ProfileCreate, ProfileOut
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
