"""ktc4 AI 모듈.

- 스크립트(scripts/*.py)에서는 sys.path에 ai/를 넣고 `src.xxx`로 import 한다(기존 방식 유지).
- BE 등 다른 프로젝트에서는 패키지로 설치해서 `ktc4_ai.xxx`로 import 한다
  (ai/pyproject.toml 에서 src/ 폴더를 ktc4_ai 라는 이름으로 배포).
  그래서 src/ 안의 모듈끼리는 반드시 상대 import(from .config import ...)를 쓴다.
"""
