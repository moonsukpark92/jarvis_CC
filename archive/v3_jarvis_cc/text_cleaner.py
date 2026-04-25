"""텍스트 정제 모듈 — Claude Code 출력을 TTS 친화적 텍스트로 변환.

참조: claude-speak cc-speak.py (35+ regex), clarvis 기술용어 변환.
"""

import re

# ─── ANSI / 터미널 장식 ──────────────────────────────────────────────────────

RE_ANSI = re.compile(
    r"\x1b\[[0-9;]*[A-Za-z]|\x1b\].*?\x07|\x1b[()][AB012]|\x1b\[[\d;]*m"
)
RE_BOX = re.compile(
    r"[─━│┃┌┐└┘├┤┬┴┼╭╮╰╯╔╗╚╝╠╣╦╩╬═║▀▄█▌▐░▒▓●○◆◇■□▪▫★☆✓✗✔✘⎿⎡⎣⎤⎦►▶◀◁▷▸▹◂◃]"
)
RE_SPINNER = re.compile(r"[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏⣷⣯⣟⡿⢿⣻⣽⣾✻◐◑◒◓⏳⌛🔄]")
RE_DECORATIVE_LINE = re.compile(
    r"^[\s─━═╌╍┈┉•·…\-_~*#=+|<>\/\\]+$", re.MULTILINE
)

# ─── 코드 블록 / 도구 호출 ──────────────────────────────────────────────────

RE_FENCED_CODE = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)
RE_INDENTED_CODE = re.compile(r"(?:^[ \t]{4,}\S.*\n){3,}", re.MULTILINE)
RE_JSON_BLOCK = re.compile(r"^\s*[\[{][\s\S]*?[\]}]\s*$", re.MULTILINE)
RE_TOOL_OUTPUT_SECTION = re.compile(
    r"^\s*⎿?\s*(?:Read|Write|Edit|Bash|Glob|Grep|Task|TodoWrite|Search)\s*\(.*\).*(?:\n(?:[ \t]+.*|\s*))*",
    re.MULTILINE,
)
RE_TOOL_TAGS = re.compile(
    r"</?(?:tool|artifact|function|parameter|result|content|antml)[^>]*>"
)
RE_TOOL_INVOKE = re.compile(
    r"^\s*(?:Read|Write|Edit|Bash|Glob|Grep|Task|TodoWrite)\s*\(.*\)\s*$",
    re.MULTILINE,
)

# ─── 경로 / URL / 명령어 ────────────────────────────────────────────────────

RE_FILE_PATH = re.compile(
    r"(?:^|\s)(?:[A-Za-z]:)?(?:[/\\][\w.\-]+){2,}(?::\d+)?", re.MULTILINE
)
RE_WIN_PATH = re.compile(r"(?:^|\s)[A-Za-z]:\\(?:[\w.\-]+\\?)+", re.MULTILINE)
RE_PATH_LINE = re.compile(
    r"^\s*(?:[A-Za-z]:)?(?:[/\\][\w.\-]+){2,}(?::\d+(?::\d+)?)?\s*$",
    re.MULTILINE,
)
RE_STANDALONE_URL = re.compile(r"(?:^|\s)(?:https?|ftp)://\S+", re.MULTILINE)
RE_COMMAND_OUTPUT = re.compile(r"^\s*[$>]\s+\S+.*$", re.MULTILINE)

# ─── 토큰 / 비용 / 진행률 ───────────────────────────────────────────────────

RE_PROGRESS = re.compile(r"\d+%\s*[|█▓▒░\-=>#\[\]]+")
RE_TOKENS = re.compile(
    r"^\s*[\d,.]+\s*(?:tokens?|tok)\b.*$", re.MULTILINE | re.IGNORECASE
)
RE_TIMING = re.compile(
    r"^\s*(?:✻\s*)?(?:Worked|Completed|Duration|Elapsed)\s+(?:for\s+)?\d+.*$",
    re.MULTILINE | re.IGNORECASE,
)
RE_COST = re.compile(
    r"^\s*(?:Cost|Tokens?|Input|Output|Cache)[\s:]+[\d$.,]+.*$",
    re.MULTILINE | re.IGNORECASE,
)
RE_DIFF = re.compile(r"^[+\-]{1,3}(?=\s)", re.MULTILINE)

# ─── 기술용어 한국어 TTS 변환 (clarvis 패턴) ────────────────────────────────

TECH_TERM_MAP = {
    "API": "에이피아이",
    "APIs": "에이피아이",
    "JSON": "제이슨",
    "JSONL": "제이슨엘",
    "HTML": "에이치티엠엘",
    "CSS": "씨에스에스",
    "HTTP": "에이치티티피",
    "HTTPS": "에이치티티피에스",
    "URL": "유알엘",
    "SQL": "에스큐엘",
    "CLI": "씨엘아이",
    "GUI": "지유아이",
    "IDE": "아이디이",
    "SDK": "에스디케이",
    "npm": "엔피엠",
    "pip": "핍",
    "git": "깃",
    "GitHub": "깃허브",
    "PyPI": "파이피아이",
    "TTS": "티티에스",
    "STT": "에스티티",
    "MCP": "엠씨피",
    "LLM": "엘엘엠",
    "AI": "에이아이",
    "GPU": "지피유",
    "CPU": "씨피유",
    "RAM": "램",
    "SSD": "에스에스디",
    "USB": "유에스비",
    "WiFi": "와이파이",
    "SAPI": "사피",
    "WAV": "웨이브",
    "MP3": "엠피쓰리",
    "TOML": "토믈",
    "YAML": "야믈",
    "ANSI": "앤시",
    "UTF-8": "유티에프 팔",
    "async": "어싱크",
    "await": "어웨이트",
    "kwargs": "키워드 아규먼트",
    "args": "아규먼트",
    "bool": "불린",
    "int": "인트",
    "str": "스트링",
    "dict": "딕셔너리",
    "list": "리스트",
    "tuple": "튜플",
    "None": "논",
    "True": "트루",
    "False": "폴스",
    "localhost": "로컬호스트",
    "README": "리드미",
    "TODO": "투두",
    "FIXME": "픽스미",
    "config": "컨피그",
    "env": "엔브",
    ".env": "닷엔브",
    "stderr": "스탠다드에러",
    "stdout": "스탠다드아웃",
    "stdin": "스탠다드인",
}

# 정규식: 기술용어 매칭 (한국어 환경에서 \b가 안 먹으므로 lookaround 사용)
# 긴 키워드부터 매칭하여 "APIs"가 "API"보다 먼저 매칭되도록
_sorted_terms = sorted(TECH_TERM_MAP.keys(), key=len, reverse=True)
_TECH_PATTERN = re.compile(
    r"(?<![A-Za-z])(" + "|".join(re.escape(k) for k in _sorted_terms) + r")(?![A-Za-z])"
)


def format_tech_terms(text: str) -> str:
    """기술용어를 한국어 TTS 친화적으로 변환."""
    return _TECH_PATTERN.sub(lambda m: TECH_TERM_MAP.get(m.group(0), m.group(0)), text)


def filter_non_speech_content(text: str) -> str:
    """비발화 콘텐츠 필터링 (코드블록, 도구 출력, JSON, 경로, URL, 명령어)."""
    text = RE_FENCED_CODE.sub("", text)
    text = RE_INDENTED_CODE.sub("", text)
    text = RE_TOOL_OUTPUT_SECTION.sub("", text)
    text = RE_JSON_BLOCK.sub("", text)
    text = RE_PATH_LINE.sub("", text)
    text = RE_STANDALONE_URL.sub("", text)
    text = RE_COMMAND_OUTPUT.sub("", text)
    return text


def clean_text(raw: str) -> str:
    """Claude Code 출력을 TTS용 깨끗한 텍스트로 변환.

    참조: claude-speak cc-speak.py clean_text() (lines 139-281).
    """
    text = raw

    # 1단계: 터미널 장식 제거
    text = RE_ANSI.sub("", text)
    text = RE_SPINNER.sub("", text)
    text = RE_BOX.sub(" ", text)
    text = RE_TOOL_TAGS.sub("", text)
    text = RE_PROGRESS.sub("", text)

    # 2단계: 메타 정보 제거
    text = RE_TOKENS.sub("", text)
    text = RE_TIMING.sub("", text)
    text = RE_COST.sub("", text)
    text = RE_TOOL_INVOKE.sub("", text)
    text = RE_DIFF.sub("", text)
    text = RE_DECORATIVE_LINE.sub("", text)

    # 3단계: 비발화 콘텐츠 필터
    text = filter_non_speech_content(text)

    # 4단계: 파일 경로 제거
    text = RE_WIN_PATH.sub(" ", text)
    text = RE_FILE_PATH.sub(" ", text)

    # 5단계: 코드블록 → [코드 블록]
    text = re.sub(r"```[^\n]*\n.*?```", "\n", text, flags=re.DOTALL)
    text = re.sub(
        r"(?:^[ \t]{4,}\S.*\n){3,}", "\n", text, flags=re.MULTILINE
    )
    # 인라인 코드: `code` → code
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # 6단계: 마크다운 정리
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)      # 링크
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)           # 이미지
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)      # 볼드/이탤릭
    text = re.sub(r"_{1,3}(\S[^_]*\S)_{1,3}", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE) # 헤더
    text = re.sub(r"^[\-*_]{3,}\s*$", "", text, flags=re.MULTILINE)  # 수평선
    text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)   # 불릿
    text = re.sub(r"^[\s]*\d+[.)]\s+", "", text, flags=re.MULTILINE) # 번호
    text = re.sub(r"<[^>]+>", "", text)                        # HTML

    # 7단계: URL 제거
    text = re.sub(r"https?://\S+", "", text)

    # 8단계: 기호 → 자연어
    text = text.replace("\u2192", " ")   # →
    text = text.replace("\u2190", " ")   # ←
    text = text.replace("=>", " ")
    text = text.replace("->", " ")
    text = text.replace("&", " 그리고 ")
    text = text.replace("|", " 또는 ")

    # 9단계: 식별자 정리
    text = re.sub(
        r"\b(\w+)_(\w+)\b",
        lambda m: m.group(0).replace("_", " ")
        if not m.group(0).startswith("__")
        else m.group(0),
        text,
    )
    text = re.sub(r"(?<=[a-z])\.(?=[a-z])", " ", text)

    # 10단계: 잡 기호 제거
    text = re.sub(r"(?<!\w)[\\$^`~](?!\w)", " ", text)
    text = re.sub(r"[{}\[\]]", " ", text)
    text = re.sub(r"([=\-_]){2,}", " ", text)

    # 11단계: 공백 정리
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    text = "\n".join(line.strip() for line in text.splitlines())

    return text.strip()


def process_for_speech(raw: str, apply_tech_terms: bool = True) -> str:
    """전체 파이프라인: 정제 + 기술용어 변환."""
    text = clean_text(raw)
    if apply_tech_terms:
        text = format_tech_terms(text)
    return text


def extract_speakable_chunks(
    text: str, max_paragraph: int = 500, max_sentence: int = 400
) -> list[str]:
    """TTS를 위해 텍스트를 적절한 크기의 청크로 분할.

    참조: claude-speak claude-speak.py lines 716-746.
    """
    if not text.strip():
        return []

    chunks: list[str] = []
    paragraphs = text.split("\n")

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(para) <= max_paragraph:
            chunks.append(para)
            continue

        # 긴 문단은 문장 단위로 분할
        sentences = re.split(r"(?<=[.!?。])\s+", para)
        current = ""
        for sentence in sentences:
            if len(current) + len(sentence) + 1 <= max_sentence:
                current = f"{current} {sentence}".strip()
            else:
                if current:
                    chunks.append(current)
                current = sentence
        if current:
            chunks.append(current)

    return chunks


if __name__ == "__main__":
    # 테스트
    test_input = """## 분석 결과

```python
def hello():
    print("world")
```

박대표님, **14번째 줄**에 `IndentationError`가 발견되었습니다.
파일 경로: C:\\Users\\infow\\project\\main.py:14

이 오류는 `if` 블록 내부의 들여쓰기가 일치하지 않아 발생합니다.
수정 방법: **4칸 스페이스**로 통일하면 됩니다.

> Cost: $0.02 | Tokens: 1,234

✻ Worked for 3.2 seconds
"""
    cleaned = process_for_speech(test_input)
    print("[정제 결과]")
    print(cleaned)
    print()

    chunks = extract_speakable_chunks(cleaned)
    print(f"[청크 {len(chunks)}개]")
    for i, chunk in enumerate(chunks, 1):
        print(f"  {i}. {chunk}")
