"""사용자 프로필 API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.profile import UserProfile
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
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return ProfileOut.model_validate(profile)
