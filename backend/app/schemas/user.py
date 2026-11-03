"""사용자 응답 스키마."""

from pydantic import BaseModel


class UserMeOut(BaseModel):
    user_id: int
    nickname: str
    email: str | None
    is_guest: bool  # 소셜 계정이 하나도 연결되지 않은 익명 사용자
    providers: list[str]  # 연결된 소셜사 (GOOGLE | KAKAO | NAVER)
