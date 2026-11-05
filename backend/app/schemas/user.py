"""사용자 응답 스키마."""

from datetime import date

from pydantic import BaseModel, Field


class UserMeOut(BaseModel):
    user_id: int
    nickname: str
    email: str | None
    is_guest: bool  # 소셜 계정이 하나도 연결되지 않은 익명 사용자
    providers: list[str]  # 연결된 소셜사 (GOOGLE | KAKAO)


class RoadmapOut(BaseModel):
    started_at: date = Field(description="서비스를 처음 쓴 날 (계정 생성 또는 첫 프로필 중 이른 날)")
    elapsed_months: int = Field(description="경과 개월 - started_at 부터 다 채운 개월 수")
    total_interest: int = Field(
        description="총 이자(세후, 원) - 지금까지 고른 모든 안에서 오늘까지 번 이자. 만기·그만둔 안 포함"
    )
    current_interest: int = Field(
        description="현재 이자(세후, 원) - 지금 진행중인 안의 만기 전 상품에서 오늘까지 쌓인 이자"
    )
    current_principal: int = Field(description="지금 진행중인 안에 오늘까지 넣은 원금(원). 목표 경로 표시용")
    active_portfolio_id: int | None = Field(description="진행중인 안. 없으면 null")
