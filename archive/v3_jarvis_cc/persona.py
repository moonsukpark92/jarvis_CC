"""JARVIS 퍼소나 — Claude Code 응답을 버틀러 스타일로 변환.

참조: clarvis src/types.ts (styles, modes), src/llm.ts (summarization).
"""

import re
from jarvis_cc.config import PersonaConfig


# 의도 감지 키워드
INTENT_PATTERNS = {
    "completion": [
        r"완료", r"수정했", r"생성했", r"추가했", r"삭제했", r"변경했",
        r"설치", r"업데이트", r"created", r"updated", r"fixed",
        r"added", r"removed", r"installed", r"completed",
    ],
    "error": [
        r"오류", r"에러", r"실패", r"문제", r"버그", r"예외",
        r"error", r"failed", r"exception", r"bug", r"issue",
        r"warning", r"경고", r"주의",
    ],
    "question": [
        r"하시겠", r"할까요", r"원하시", r"선택", r"결정",
        r"확인.*부탁", r"어떻게.*할까",
        r"would you", r"should I", r"do you want",
    ],
    "status": [
        r"분석 중", r"처리 중", r"검색 중", r"확인 중",
        r"analyzing", r"processing", r"searching", r"checking",
    ],
}

# 퍼소나 접두어 템플릿
PERSONA_TEMPLATES = {
    "butler": {
        "completion": "{owner}, {summary} 처리를 완료했습니다.",
        "error": "{owner}, 주의가 필요한 사항이 있습니다. {summary}",
        "question": "{owner}, 확인이 필요합니다. {summary}",
        "status": "{owner}, {summary} 진행 중입니다.",
        "default": "{owner}, {summary}",
    },
    "casual": {
        "completion": "{summary} 다 됐어요!",
        "error": "앗, 문제가 있네요. {summary}",
        "question": "{summary} 어떻게 할까요?",
        "status": "{summary} 하는 중이에요.",
        "default": "{summary}",
    },
    "professional": {
        "completion": "{summary} 완료되었습니다.",
        "error": "이슈가 발견되었습니다. {summary}",
        "question": "결정이 필요합니다. {summary}",
        "status": "{summary} 진행 중입니다.",
        "default": "{summary}",
    },
}

# 모드별 최대 길이
MODE_MAX_LENGTH = {
    "brief": 80,
    "normal": 200,
    "full": 0,       # 제한 없음
    "bypass": 0,     # 정제만, 포맷 없음
}


class JarvisPersona:
    """JARVIS 퍼소나 포맷 변환기."""

    def __init__(self, config: PersonaConfig):
        self.config = config
        self._templates = PERSONA_TEMPLATES.get(config.style, PERSONA_TEMPLATES["butler"])

    def detect_intent(self, text: str) -> str:
        """텍스트에서 의도 자동 감지."""
        text_lower = text.lower()
        scores = {}

        for intent, patterns in INTENT_PATTERNS.items():
            score = sum(1 for p in patterns if re.search(p, text_lower))
            if score > 0:
                scores[intent] = score

        if not scores:
            return "default"
        return max(scores, key=scores.get)

    def auto_select_mode(self, text: str) -> str:
        """텍스트 길이/유형에 따라 모드 자동 선택."""
        length = len(text)
        if length < 100:
            return "brief"
        elif length < 500:
            return "normal"
        else:
            return "full"

    def summarize(self, text: str, max_length: int) -> str:
        """텍스트를 지정 길이로 요약 (단순 잘라내기 + 문장 경계)."""
        if max_length <= 0 or len(text) <= max_length:
            return text

        # 문장 경계에서 자르기
        truncated = text[:max_length]
        # 마지막 문장 끝 찾기
        for end_char in [".", "。", "!", "?", "다.", "요."]:
            last_pos = truncated.rfind(end_char)
            if last_pos > max_length * 0.5:
                return truncated[: last_pos + len(end_char)]

        # 마지막 공백에서 자르기
        last_space = truncated.rfind(" ")
        if last_space > max_length * 0.5:
            return truncated[:last_space] + "..."

        return truncated + "..."

    def format_response(self, raw_text: str, mode: str | None = None) -> str:
        """Claude 응답 → JARVIS 퍼소나 포맷 변환.

        Args:
            raw_text: 정제된(clean) 텍스트
            mode: brief/normal/full/bypass (None이면 자동)
        """
        if not raw_text.strip():
            return ""

        # 모드 결정
        if mode is None:
            mode = self.config.mode
        if mode == "auto":
            mode = self.auto_select_mode(raw_text)

        # bypass: 포맷 없이 그대로
        if mode == "bypass":
            return raw_text

        # 요약
        max_len = MODE_MAX_LENGTH.get(mode, 200)
        summary = self.summarize(raw_text, max_len)

        # 의도 감지
        intent = self.detect_intent(raw_text)

        # 템플릿 적용
        template = self._templates.get(intent, self._templates["default"])
        formatted = template.format(
            owner=self.config.owner_name,
            summary=summary,
        )

        return formatted

    def format_greeting(self) -> str:
        """활성화 인사말."""
        greetings = {
            "butler": f"네, {self.config.owner_name}. 말씀하세요.",
            "casual": "네, 듣고 있어요!",
            "professional": f"{self.config.owner_name}, 준비되었습니다.",
        }
        return greetings.get(self.config.style, greetings["butler"])

    def format_farewell(self) -> str:
        """비활성화 인사말."""
        farewells = {
            "butler": f"{self.config.owner_name}, 대기 모드로 전환합니다.",
            "casual": "알겠어요, 필요하면 부르세요!",
            "professional": "대기 모드입니다.",
        }
        return farewells.get(self.config.style, farewells["butler"])


if __name__ == "__main__":
    config = PersonaConfig()
    persona = JarvisPersona(config)

    test_cases = [
        "14번째 줄에 IndentationError가 발견되었습니다. if 블록 내부의 들여쓰기를 수정했습니다.",
        "requirements.txt 파일이 존재하지 않습니다. 새로 생성할까요?",
        "분석을 완료했습니다. 총 3개의 파일을 수정했습니다. main.py에서 import 순서를 정리하고, config.py에서 기본값을 업데이트하고, test_main.py에 새 테스트 케이스를 추가했습니다.",
        "현재 코드를 분석 중입니다.",
    ]

    for text in test_cases:
        intent = persona.detect_intent(text)
        for mode in ["brief", "normal", "full"]:
            result = persona.format_response(text, mode)
            print(f"[{mode}/{intent}] {result}")
        print()

    print(f"[greeting] {persona.format_greeting()}")
    print(f"[farewell] {persona.format_farewell()}")
