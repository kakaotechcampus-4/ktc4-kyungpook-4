"""로그인 계정·세션 관리.

Redis 에는 날아가도 되는 것만 둔다. state 가 날아가면 로그인을 다시 누르면 되고,
refresh 토큰이 날아가면 다시 로그인하면 된다. 계정 자체는 항상 PostgreSQL 에 있다.
"""

import json
import secrets

from redis.asyncio import Redis
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_token, new_refresh_token
from app.models.manual_entry import UserManualEntry
from app.models.portfolio import UserPortfolio
from app.models.profile import UserProfile
from app.models.user import AppUser, SocialAccount
from app.services.oauth import SocialUser
from app.services.portfolio import close_active_portfolios

STATE_TTL_SECONDS = 600  # 소셜사 로그인 화면에서 머무를 수 있는 시간
# 교체된 refresh 토큰을 이 시간 동안은 받아준다. 동시에 나간 refresh 요청이 로그아웃되지 않게 하기 위해서다
REFRESH_GRACE_SECONDS = 30
DEFAULT_NICKNAME = "사용자"  # 소셜사가 닉네임을 안 주면 (app_user.nickname 은 NOT NULL)
_NICKNAME_MAX = 50


def _state_key(state: str) -> str:
    return f"auth:state:{state}"


def _refresh_key(token: str) -> str:
    return f"auth:refresh:{hash_token(token)}"


def _rotated_key(token: str) -> str:
    return f"auth:refresh-rotated:{hash_token(token)}"


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


async def adopt_guest(session: AsyncSession, guest_id: int, user_id: int) -> None:
    """로그인 전에 게스트로 만든 프로필·포트폴리오를 로그인한 계정으로 옮기고 게스트를 지운다.

    게스트 쪽에 진행중인 안이 있으면 그게 더 최근에 고른 안이므로 계정 쪽 진행중 안을 그만둔다.
    """
    if guest_id == user_id:
        return
    is_social = await session.scalar(select(SocialAccount.social_id).where(SocialAccount.user_id == guest_id).limit(1))
    if is_social is not None or await session.get(AppUser, guest_id) is None:
        return  # 게스트가 아니거나 이미 옮겨졌다

    guest_active = await session.scalar(
        select(UserPortfolio.portfolio_id)
        .where(UserPortfolio.user_id == guest_id, UserPortfolio.status == "진행중")
        .limit(1)
    )
    if guest_active is not None:
        await close_active_portfolios(session, user_id)
    for model in (UserProfile, UserPortfolio, UserManualEntry):
        await session.execute(update(model).where(model.user_id == guest_id).values(user_id=user_id))
    await session.execute(delete(AppUser).where(AppUser.user_id == guest_id))
    await session.commit()


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


async def rotate_refresh(redis: Redis, token: str) -> tuple[int, str | None] | None:
    """refresh 토큰을 새로 바꾼다. (user_id, 새 refresh) 를 주고, 유효하지 않으면 None.

    access 가 만료되면 여러 요청이 동시에 같은 refresh 토큰으로 들어온다 (탭 여러 개, 이미 보낸 요청).
    쓰자마자 지우면 첫 요청만 성공하고 나머지는 실패해 로그아웃되므로:
    - 교체는 SET NX 로 한 요청만 한다 (원자적). 그 요청만 새 refresh 를 받고, 옛 토큰 수명은 유예 시간으로 줄인다
    - 나머지는 옛 토큰이 살아 있는 유예 시간 동안 새 refresh 없이 (user_id, None) 을 받는다 → access 만 재발급.
      브라우저는 교체한 요청의 응답이 준 새 refresh 를 이미 갖고 있어서 그대로 두면 된다
    - 유예 시간이 지나면 옛 토큰은 만료돼 None
    """
    user_id = await redis.get(_refresh_key(token))
    if user_id is None:
        return None
    if not await redis.set(_rotated_key(token), 1, nx=True, ex=REFRESH_GRACE_SECONDS):
        return int(user_id), None
    await redis.expire(_refresh_key(token), REFRESH_GRACE_SECONDS)
    return int(user_id), await issue_refresh(redis, int(user_id))


async def revoke_refresh(redis: Redis, token: str) -> None:
    await redis.delete(_refresh_key(token))
