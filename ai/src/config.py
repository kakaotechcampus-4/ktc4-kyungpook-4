"""환경변수 로드 - API 키 등 민감정보는 여기서만 읽는다."""
import os
from dotenv import load_dotenv

load_dotenv()

FSS_AUTH_KEY = os.getenv("FSS_AUTH_KEY", "")

# 엘리스 ML API (OpenAI 호환) - Extraction/Summary 둘 다 Claude Sonnet 5로 통일
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "anthropic/claude-sonnet-5")

if not FSS_AUTH_KEY:
    print("[경고] FSS_AUTH_KEY가 .env에 설정되지 않았습니다.")
if not OPENAI_API_KEY:
    print("[경고] OPENAI_API_KEY가 .env에 설정되지 않았습니다.")
if not OPENAI_BASE_URL:
    print("[경고] OPENAI_BASE_URL이 .env에 설정되지 않았습니다.")