"""
ai/scripts 폴더 안의 모든 .py 파일을 스캔해서
1) AI/LLM API를 실제로 호출하는 코드가 있는지 (openai, anthropic, gpt, requests.post 등)
2) build_erd_tables.py가 그 파일들을 실제로 import하거나 함수/결과물을 갖다 쓰는지
를 자동으로 확인한다. (내가 직접 파일을 열어볼 수 없어서, 코드가 대신 확인하는 스크립트)
"""
import re
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent

AI_PATTERNS = {
    "openai 패키지/API": re.compile(r"\bopenai\b", re.IGNORECASE),
    "anthropic 패키지/API": re.compile(r"\banthropic\b", re.IGNORECASE),
    "gpt 모델명": re.compile(r"gpt-?\d|gpt4|gpt3", re.IGNORECASE),
    "claude 모델명": re.compile(r"claude-?\d|claude-3|claude-sonnet|claude-opus|claude-haiku", re.IGNORECASE),
    "chat completion 호출": re.compile(r"chat\.completions|messages\.create|ChatCompletion", re.IGNORECASE),
    "API 키 사용": re.compile(r"api_key|API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY"),
    "langchain": re.compile(r"langchain", re.IGNORECASE),
    "임베딩/LLM 관련어": re.compile(r"embedding|\bllm\b|prompt\s*=|system_prompt", re.IGNORECASE),
    "외부 HTTP 호출(requests/httpx)": re.compile(r"requests\.(get|post)|httpx\.(get|post)"),
}

py_files = sorted(SCRIPTS.glob("*.py"))
if not py_files:
    print(f"[!] {SCRIPTS} 안에 .py 파일이 없습니다. 이 스크립트를 ai\\scripts 폴더 안에 놓고 실행해주세요.")
else:
    print(f"=== {SCRIPTS} 안의 .py 파일 {len(py_files)}개 스캔 결과 ===\n")
    for f in py_files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"[{f.name}] 읽기 실패: {e}")
            continue
        hits = []
        for label, pattern in AI_PATTERNS.items():
            if pattern.search(text):
                hits.append(label)
        if hits:
            print(f"[{f.name}]  AI/LLM 관련 흔적 있음 -> {', '.join(hits)}")
        else:
            print(f"[{f.name}]  AI/LLM 관련 흔적 없음")

    print()
    print("=" * 70)
    print()

    build_path = SCRIPTS / "build_erd_tables.py"
    if build_path.exists():
        build_text = build_path.read_text(encoding="utf-8", errors="ignore")
        print("=== build_erd_tables.py가 다른 스크립트를 참조하는지 확인 ===\n")
        referenced = []
        for f in py_files:
            if f.name == "build_erd_tables.py":
                continue
            stem = f.stem
            if re.search(rf"\b{re.escape(stem)}\b", build_text):
                referenced.append(f.name)
        if referenced:
            print("build_erd_tables.py 안에서 언급/참조되는 파일:")
            for r in referenced:
                print(f"  - {r}")
        else:
            print("build_erd_tables.py는 ai/scripts 폴더의 다른 파일을 전혀 import하거나 참조하지 않음")
            print("(= 완전히 독립적으로, 원본 JSON/JSONL 데이터만 직접 읽어서 처리)")
    else:
        print("[!] build_erd_tables.py를 같은 폴더에서 찾을 수 없습니다.")

    print()
    print("=" * 70)
    print()
    print("=== 특히 이름이 의심스러운 4개 파일의 앞부분 30줄만 미리보기 ===\n")
    SUSPECTS = [
        "test_extraction_verify.py",
        "extract_verify_cu_saving.py",
        "check_ml_api_models.py",
        "test_ml_api.py",
    ]
    for name in SUSPECTS:
        p = SCRIPTS / name
        if not p.exists():
            print(f"--- {name}: 파일 없음 ---\n")
            continue
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        print(f"--- {name} (앞 30줄) ---")
        for line in lines[:30]:
            print(" ", line)
        print()