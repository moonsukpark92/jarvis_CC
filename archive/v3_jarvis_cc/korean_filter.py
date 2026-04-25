"""한국어 인식 필터 — Whisper STT 오인식 교정.

faster-whisper의 한국어 오인식 패턴을 교정합니다.
- 웨이크워드 유사도 매칭 (자비스/자피스/가비스 등)
- 자주 발생하는 초성 혼동 교정
- 빈 결과/노이즈 필터링
"""

import logging
import re
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# ─── 웨이크워드 유사도 매칭 ───────────────────────────────────────────────

# 기준 웨이크워드
WAKE_WORD = "자비스"

# 알려진 오인식 변형 (직접 매핑)
WAKE_WORD_VARIANTS = {
    "자비스", "자피스", "가비스", "자 비스", "자비쓰", "자부스",
    "아비스", "하비스", "져비스", "쟈비스", "자비",
    "자 빗", "자빗", "자빛", "잡이스", "자뷔스",
    "자비수", "차비스", "자비으", "자비시",
    "자밑", "자빕", "자밋", "자벼스", "자볏",
}

# 영어 변형
WAKE_WORD_EN_VARIANTS = {
    "jarvis", "javis", "jarvice", "jarves", "jervis",
    "jarbus", "jobis", "jarbis",
}


def is_wake_word(text: str, threshold: float = 0.5) -> bool:
    """텍스트에 웨이크워드가 포함되어 있는지 유사도 기반으로 판단.

    Args:
        text: STT 결과 텍스트
        threshold: 유사도 임계값 (0.0~1.0, 낮을수록 느슨)

    Returns:
        웨이크워드 포함 여부
    """
    if not text or not text.strip():
        return False

    text_lower = text.lower().strip()

    # 구두점/공백 제거 버전도 준비
    text_clean = re.sub(r"[,.\s!?~\-·、。！？]", "", text_lower)

    # 1단계: 직접 매핑 확인 (원본 + 클린)
    for variant in WAKE_WORD_VARIANTS:
        clean_variant = re.sub(r"[\s]", "", variant)
        if variant in text_lower or clean_variant in text_clean:
            return True

    for variant in WAKE_WORD_EN_VARIANTS:
        if variant in text_lower or variant in text_clean:
            return True

    # 2단계: 교정 후 재확인
    corrected = correct_korean(text_lower)
    if corrected != text_lower:
        for variant in WAKE_WORD_VARIANTS:
            if variant in corrected:
                return True

    # 3단계: 유사도 매칭 (클린 텍스트의 각 2~4글자 윈도우)
    check_text = text_clean if text_clean else text_lower
    for window_size in [2, 3, 4]:
        for i in range(len(check_text) - window_size + 1):
            window = check_text[i:i + window_size]
            similarity = SequenceMatcher(None, WAKE_WORD, window).ratio()
            if similarity >= threshold:
                logger.debug(f"Wake word match: '{window}' ~ '{WAKE_WORD}' ({similarity:.2f})")
                return True

    return False


# ─── 한국어 STT 교정 ────────────────────────────────────────────────────

# 자주 발생하는 초성 혼동 패턴 (Whisper tiny 한국어)
CORRECTION_PATTERNS = [
    # (오인식 패턴, 교정)
    (r"기후부터", "지금부터"),
    (r"기후", "지금"),
    (r"아랑과", "그런가"),
    (r"란시아", "날씨"),
    (r"제자리 룰", "제자리 룰"),  # 이건 맞을 수 있음
    (r"탑시", "자비스"),
    (r"잘생겼습니다", ""),  # 노이즈
    (r"이 야예인군", ""),   # 노이즈
]

# 노이즈/무의미 패턴 (필터링)
NOISE_PATTERNS = [
    r"^\.+$",                    # 마침표만
    r"^네\.?$",                  # "네" 단독 (확인 응답)
    r"^그[럼래면]\.?$",           # "그럼" 단독
    r"^음+\.?$",                 # "음" 단독
    r"^아+\.?$",                 # "아" 단독
    r"^MBC 뉴스",                # 잡음에서 자주 나옴
    r"^자막 제공",               # 잡음에서 자주 나옴
    r"시청해 주셔서 감사합니다",   # Whisper 환각
    r"구독과 좋아요",             # Whisper 환각
]


def correct_korean(text: str) -> str:
    """한국어 STT 결과를 교정합니다.

    Args:
        text: STT 원본 텍스트

    Returns:
        교정된 텍스트
    """
    if not text:
        return text

    result = text

    # 교정 패턴 적용
    for pattern, replacement in CORRECTION_PATTERNS:
        result = re.sub(pattern, replacement, result)

    return result.strip()


def is_noise(text: str) -> bool:
    """노이즈/무의미 텍스트인지 판단.

    Whisper는 무음/잡음에서 "환각"을 생성하는 경향이 있음.
    """
    if not text or len(text.strip()) < 2:
        return True

    text_stripped = text.strip()

    for pattern in NOISE_PATTERNS:
        if re.match(pattern, text_stripped):
            return True

    return False


def filter_korean_stt(text: str) -> str | None:
    """STT 결과를 필터링하고 교정합니다.

    Returns:
        교정된 텍스트, 노이즈인 경우 None
    """
    if is_noise(text):
        logger.debug(f"Filtered noise: '{text}'")
        return None

    corrected = correct_korean(text)
    if not corrected:
        return None

    if corrected != text:
        logger.info(f"Korean correction: '{text}' → '{corrected}'")

    return corrected


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 웨이크워드 테스트
    test_words = [
        "자비스", "자피스", "가비스", "자 빗", "자, 빛!",
        "아비스", "jarvis", "안녕하세요", "좋은 아침",
        "자비스 안녕", "나는 자 빗으라고 했는데",
    ]
    print("=== 웨이크워드 유사도 매칭 ===")
    for word in test_words:
        result = is_wake_word(word)
        print(f"  '{word}' -> {'WAKE' if result else 'skip'}")

    print()

    # 교정 테스트
    test_corrections = [
        "기후부터 대화가 안하는데요",
        "아랑과 속도를 좀 알려야 할 수 없어?",
        "탑시!",
        "",
        "네.",
        "MBC 뉴스 김지연입니다",
        "자비스가 많아서 속도를 빨리 해줘요",
    ]
    print("=== 한국어 교정 필터 ===")
    for text in test_corrections:
        filtered = filter_korean_stt(text)
        print(f"  '{text}' → {repr(filtered)}")
