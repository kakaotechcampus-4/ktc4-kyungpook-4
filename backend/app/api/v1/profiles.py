"""사용자 프로필 API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.institution import Institution
from app.models.profile import UserProfile, UserProfileBank
from app.models.user import AppUser
from app.schemas.profile import ProfileCreate, ProfileOut

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("", response_model=ProfileOut, status_code=201, summary="입력값 스냅샷 생성 (STEP1)")
async def create_profile(
    body: ProfileCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProfileOut:
    if body.lump_sum == 0 and body.monthly_saving == 0:
        raise HTTPException(status_code=422, detail="목돈 또는 월 저축액 중 하나는 0보다 커야 합니다")

    held_bank_codes = list(dict.fromkeys(body.held_bank_codes))  # 순서 유지 중복 제거
    requested_codes = set(held_bank_codes) | ({body.main_bank_code} if body.main_bank_code else set())
    if requested_codes:
        # FK 위반으로 500 이 나기 전에, 없는 코드는 422 로 돌려준다
        found = set(
            (
                await session.execute(
                    select(Institution.institution_code).where(Institution.institution_code.in_(requested_codes))
                )
            ).scalars()
        )
        if unknown := sorted(requested_codes - found):
            raise HTTPException(status_code=422, detail=f"존재하지 않는 institution_code: {unknown}")

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
        main_bank_code=body.main_bank_code,
        banks=[UserProfileBank(institution_code=code) for code in held_bank_codes],
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
        created_at=profile.created_at,
    )
