"""로그인 토큰·리다이렉트 경로·소셜사 응답 해석. DB 없이 돈다."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token
from app.services.auth import safe_next
from app.services.oauth import OAuthError, _parse_google, _parse_kakao, _parse_naver

SECRET = "unit-test-secret-" + "x" * 32


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET", SECRET)


def test_access_token_roundtrip():
    assert decode_access_token(create_access_token(42)) == 42


def test_expired_token_is_rejected():
    past = datetime.now(UTC) - timedelta(minutes=1)
    token = jwt.encode({"sub": "42", "exp": past}, SECRET, algorithm="HS256")
    assert decode_access_token(token) is None


def test_token_signed_with_other_secret_is_rejected():
    token = jwt.encode({"sub": "42", "exp": datetime.now(UTC) + timedelta(minutes=5)}, "other-" + SECRET, "HS256")
    assert decode_access_token(token) is None


@pytest.mark.parametrize("token", ["", "garbage", "a.b.c"])
def test_malformed_token_is_rejected(token):
    assert decode_access_token(token) is None


def test_empty_secret_never_issues_or_accepts(monkeypatch):
    token = create_access_token(42)
    monkeypatch.setattr(settings, "JWT_SECRET", "")
    assert decode_access_token(token) is None
    with pytest.raises(RuntimeError):
        create_access_token(42)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/result", "/result"),
        ("/result?profile_id=3", "/result?profile_id=3"),
        (None, "/"),
        ("", "/"),
        ("result", "/"),
        ("//evil.com", "/"),
        ("https://evil.com", "/"),
        ("/\\evil.com", "/"),
    ],
)
def test_safe_next(raw, expected):
    assert safe_next(raw) == expected


def _fields(user):
    return (user.provider, user.provider_user_id, user.email, user.nickname)


def test_parse_google():
    user = _parse_google({"sub": "1234", "email": "a@gmail.com", "email_verified": True, "name": "덕환"})
    assert _fields(user) == ("GOOGLE", "1234", "a@gmail.com", "덕환")


def test_parse_kakao_without_email():
    # 비즈 앱이 아니면 이메일이 안 온다
    user = _parse_kakao({"id": 987654321, "kakao_account": {"profile": {"nickname": "덕환"}}})
    assert _fields(user) == ("KAKAO", "987654321", None, "덕환")


def test_parse_naver():
    user = _parse_naver({"resultcode": "00", "response": {"id": "abc", "email": "a@naver.com", "nickname": "덕환"}})
    assert _fields(user) == ("NAVER", "abc", "a@naver.com", "덕환")


def test_parse_naver_failure_code():
    with pytest.raises(OAuthError):
        _parse_naver({"resultcode": "024", "message": "Authentication failed"})
