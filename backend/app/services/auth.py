"""로그인 계정·세션 관리.

Redis 에는 날아가도 되는 것만 둔다. state 가 날아가면 로그인을 다시 누르면 되고,
refresh 토큰이 날아가면 다시 로그인하면 된다. 계정 자체는 항상 PostgreSQL 에 있다.
"""

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass

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
APP_CODE_TTL_SECONDS = 60  # 앱이 딥링크로 받은 일회용 코드를 토큰으로 바꿔야 하는 시간
DEFAULT_NICKNAME = "사용자"  # 소셜사가 닉네임을 안 주면 (app_user.nickname 은 NOT NULL)
_NICKNAME_MAX = 50


def _state_key(state: str) -> str:
    return f"auth:state:{state}"


def _refresh_key(token: str) -> str:
    return f"auth:refresh:{hash_token(token)}"


def _app_code_key(code: str) -> str:
    return f"auth:appcode:{hash_token(code)}"


@dataclass(frozen=True)
class LoginState:
    next_path: str  # 웹: 로그인 후 돌아갈 FE 경로
    client: str = "web"  # web | app
    code_challenge: str | None = None  # 앱만. PKCE S256 - 일회용 코드를 가로채도 못 쓰게 한다


def safe_next(next_path: str | None) -> str:
    """로그인 후 돌아갈 FE 경로. 우리 앱 안의 경로만 허용한다 (오픈 리다이렉트 방지)."""
    if not next_path or not next_path.startswith("/") or next_path.startswith("//") or "\\" in next_path:
        return "/"
    return next_path


async def create_state(
    redis: Redis, provider: str, next_path: str, *, client: str = "web", code_challenge: str | None = None
) -> str:
    """CSRF 방지용 state. 콜백에서 한 번만 쓸 수 있다. 앱 로그인이면 PKCE challenge 도 같이 둔다."""
    state = secrets.token_urlsafe(32)
    data = {"provider": provider, "next": next_path, "client": client, "code_challenge": code_challenge}
    await redis.set(_state_key(state), json.dumps(data), ex=STATE_TTL_SECONDS)
    return state


async def consume_state(redis: Redis, state: str, provider: str) -> LoginState | None:
    """유효하면 로그인 시작 정보, 없거나·만료됐거나·다른 provider 것이면 None. 확인과 동시에 지운다."""
    raw = await redis.getdel(_state_key(state))
    if raw is None:
        return None
    data = json.loads(raw)
    if data.get("provider") != provider:
        return None
    # client 가 없는 state 는 이 기능 전에 만든 웹 로그인이다
    return LoginState(safe_next(data.get("next")), data.get("client") or "web", data.get("code_challenge"))


def pkce_challenge(verifier: str) -> str:
    """RFC 7636 S256: BASE64URL(SHA256(verifier)), '=' 패딩 없이."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


async def create_app_code(redis: Redis, user_id: int, code_challenge: str) -> str:
    """앱 로그인 콜백에서 딥링크로 넘길 일회용 코드. 토큰을 주소에 싣지 않기 위해 한 번 더 바꾼다."""
    code = secrets.token_urlsafe(32)
    data = json.dumps({"user_id": user_id, "code_challenge": code_challenge})
    await redis.set(_app_code_key(code), data, ex=APP_CODE_TTL_SECONDS)
    return code


async def consume_app_code(redis: Redis, code: str, code_verifier: str) -> int | None:
    """맞으면 user_id. 없거나·만료됐거나·verifier 가 틀리면 None. 틀려도 코드는 지운다(재시도 공격 차단)."""
    raw = await redis.getdel(_app_code_key(code))
    if raw is None:
        return None
    data = json.loads(raw)
    if not secrets.compare_digest(pkce_challenge(code_verifier), data["code_challenge"]):
        return None
    return int(data["user_id"])


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


async def rotate_refresh(redis: Redis, token: str) -> tuple[int, str] | None:
    """쓴 refresh 토큰은 지우고 새로 발급한다. 이미 쓴 토큰을 다시 내면 None."""
    user_id = await redis.getdel(_refresh_key(token))
    if user_id is None:
        return None
    return int(user_id), await issue_refresh(redis, int(user_id))


async def revoke_refresh(redis: Redis, token: str) -> None:
    await redis.delete(_refresh_key(token))
