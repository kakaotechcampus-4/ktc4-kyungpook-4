"""캘린더 직접 기록 API. 로그인한 사용자 본인 기록만 다룬다."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.manual_entry import UserManualEntry
from app.models.product import Product
from app.models.user import AppUser
from app.schemas.manual_entry import ManualEntryCreate, ManualEntryOut

router = APIRouter(prefix="/manual-entries", tags=["manual-entries"])

_LOGIN_REQUIRED = {401: {"description": "로그인 필요 (access 토큰 만료면 /auth/refresh)"}}


@router.post("", response_model=ManualEntryOut, status_code=201, summary="직접 기록 저장", responses=_LOGIN_REQUIRED)
async def create_manual_entry(
    body: ManualEntryCreate,
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserManualEntry:
    if body.product_id is not None and await session.get(Product, body.product_id) is None:
        raise HTTPException(status_code=422, detail=f"존재하지 않는 product_id: {body.product_id}")
    entry = UserManualEntry(user_id=user.user_id, **body.model_dump())
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


@router.get(
    "",
    response_model=list[ManualEntryOut],
    summary="기간 안의 직접 기록 (캘린더 1주 단위)",
    responses=_LOGIN_REQUIRED,
)
async def list_manual_entries(
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    start: Annotated[date | None, Query(description="이 날짜부터 (포함). 생략하면 처음부터")] = None,
    end: Annotated[date | None, Query(description="이 날짜까지 (포함). 생략하면 끝까지")] = None,
) -> list[UserManualEntry]:
    if start is not None and end is not None and end < start:
        raise HTTPException(status_code=422, detail="end 는 start 보다 빠를 수 없습니다")
    stmt = select(UserManualEntry).where(UserManualEntry.user_id == user.user_id)
    if start is not None:
        stmt = stmt.where(UserManualEntry.entry_date >= start)
    if end is not None:
        stmt = stmt.where(UserManualEntry.entry_date <= end)
    stmt = stmt.order_by(UserManualEntry.entry_date, UserManualEntry.entry_id)
    return list((await session.execute(stmt)).scalars())


@router.delete(
    "/{entry_id}",
    status_code=204,
    summary="직접 기록 삭제",
    responses={**_LOGIN_REQUIRED, 404: {"description": "없거나 다른 사람의 기록"}},
)
async def delete_manual_entry(
    entry_id: int,
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    entry = await session.get(UserManualEntry, entry_id)
    if entry is None or entry.user_id != user.user_id:  # 남의 기록이 있다는 것도 알려주지 않는다
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")
    await session.delete(entry)
    await session.commit()
    return Response(status_code=204)
