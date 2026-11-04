"""로그인 계정·세션 관리.

Redis 에는 날아가도 되는 것만 둔다. state 가 날아가면 로그인을 다시 누르면 되고,
refresh 토큰이 날아가면 다시 로그인하면 된다. 계정 자체는 항상 PostgreSQL 에 있다.
"""

import json
import secrets

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_token, new_refresh_token
from app.models.user import AppUser, SocialAccount
from app.services.oauth import SocialUser

STATE_TTL_SECONDS = 600  # 소셜사 로그인 화면에서 머무를 수 있는 시간
DEFAULT_NICKNAME = "사용자"  # 소셜사가 닉네임을 안 주면 (app_user.nickname 은 NOT NULL)
_NICKNAME_MAX = 50


def _state_key(state: str) -> str:
    return f"auth:state:{state}"


def _refresh_key(token: str) -> str:
    return f"auth:refresh:{hash_token(token)}"


def safe_next(next_path: str | None) -> str:
    """로그인 후 돌아갈 FE 경로. 우리 앱 안의 경로만 허용한다 (오픈 리다이렉트 방지)."""
    if not next_path or not next_path.startswith("/") or next_path.startswith("//") or "\\" in next_path:
        return "/"
    return next_path


async def create_state(redis: Redis, provider: str, next_path: str) -> str:
    """CSRF 방지용 state. 콜백에서 한 번만 쓸 수 있다."""
    state = secrets.token_urlsafe(32)
    await redis.set(_state_key(state), json.dumps({"provider": provider, "next": next_path}), ex=STATE_TTL_SECONDS)
    return state


async def consume_state(redis: Redis, state: str, provider: str) -> str | None:
    """유효하면 돌아갈 경로, 없거나·만료됐거나·다른 provider 것이면 None. 확인과 동시에 지운다."""
    raw = await redis.getdel(_state_key(state))
    if raw is None:
        return None
    data = json.loads(raw)
    if data.get("provider") != provider:
        return None
    return safe_next(data.get("next"))


async def find_or_create_user(session: AsyncSession, social: SocialUser) -> int:
    """(provider, provider_user_id) 로 기존 회원을 찾고, 없으면 가입시킨다.

    이메일이 같아도 다른 소셜 계정과 합치지 않는다. 소셜사마다 이메일 검증 수준이 달라
    자동으로 합치면 남의 계정에 로그인되는 경로가 생긴다.
    """
    user_id = await _find_user_id(session, social)
    if user_id is not None:
        return user_id

    user = AppUser(
        nickname=(social.nickname or DEFAULT_NICKNAME)[:_NICKNAME_MAX],
        email=social.email,
        social_accounts=[
            SocialAccount(
                provider=social.provider,
                provider_user_id=social.provider_user_id,
                provider_email=social.email,
            )
        ],
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        # 같은 사람이 동시에 첫 로그인을 두 번 하면 UNIQUE 에 걸린다. 먼저 들어간 쪽을 쓴다.
        await session.rollback()
        user_id = await _find_user_id(session, social)
        if user_id is None:
            raise
        return user_id
    return user.user_id


async def _find_user_id(session: AsyncSession, social: SocialUser) -> int | None:
    return await session.scalar(
        select(SocialAccount.user_id).where(
            SocialAccount.provider == social.provider,
            SocialAccount.provider_user_id == social.provider_user_id,
        )
    )


async def issue_refresh(redis: Redis, user_id: int) -> str:
    token = new_refresh_token()
    await redis.set(_refresh_key(token), user_id, ex=settings.REFRESH_TOKEN_DAYS * 86400)
    return token


async def rotate_refresh(redis: Redis, token: str) -> tuple[int, str] | None:
    """쓴 refresh 토큰은 지우고 새로 발급한다. 이미 쓴 토큰을 다시 내면 None."""
    user_id = await redis.getdel(_refresh_key(token))
    if user_id is None:
        return None
    return int(user_id), await issue_refresh(redis, int(user_id))


async def revoke_refresh(redis: Redis, token: str) -> None:
    await redis.delete(_refresh_key(token))
