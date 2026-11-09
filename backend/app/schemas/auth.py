"""앱(안드로이드) 로그인 요청/응답 스키마. 웹은 쿠키만 쓰므로 이 스키마를 쓰지 않는다."""

from pydantic import BaseModel, Field

# RFC 7636: verifier 는 43~128자, 영문·숫자와 - . _ ~ 만
PKCE_VERIFIER_PATTERN = r"^[A-Za-z0-9\-._~]{43,128}$"
# S256 challenge = SHA-256 을 패딩 없는 base64url 로 = 항상 43자
PKCE_CHALLENGE_PATTERN = r"^[A-Za-z0-9\-_]{43}$"


class AppTokenRequest(BaseModel):
    code: str = Field(description="로그인 후 딥링크(safebrother://auth?code=...)로 받은 일회용 코드. 60초 유효")
    code_verifier: str = Field(pattern=PKCE_VERIFIER_PATTERN, description="로그인 시작 때 만든 PKCE verifier 원문")
    guest_token: str | None = Field(
        default=None, description="로그인 전에 쓰던 게스트 토큰. 주면 그 게스트의 기록을 로그인 계정으로 옮긴다"
    )


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str = Field(description="API 요청마다 Authorization: Bearer <access_token> 으로 보낸다")
    refresh_token: str = Field(description="access 만료(401) 시 POST /auth/refresh 에 보낸다. 쓰면 새 것으로 바뀐다")
    token_type: str = "bearer"
    expires_in: int = Field(description="access_token 유효 시간(초)")


class GuestTokenOut(BaseModel):
    guest_token: str = Field(description="로그인 전 기록의 주인 표시. Authorization: Bearer <guest_token> 으로 보낸다")
