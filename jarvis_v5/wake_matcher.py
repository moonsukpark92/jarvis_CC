"""웨이크워드 엄격 매칭 — "데비스" 호출만 반응.

엄격 모드: 유사도 0.75 이상 + 키워드 독립성 체크.
TV/배경 소리로 인한 오탐 최소화.
"""

import logging
import re
from difflib import SequenceMatcher
from typing import Optional

logger = logging.getLogger("davis.wake")

# 정확한 웨이크워드 (가장 높은 가중치)
PRIMARY_VARIANTS = {
    "데비스", "데뷔스", "데비쓰", "대비스", "davis",
    "데빗", "대빗", "데비",
}

# 유사 변형 (낮은 가중치, 유사도 체크 필요)
SECONDARY_VARIANTS = {
    "데빗", "대빗", "데비수", "테비스", "데비",
    "더비스", "대비수",
}

# 명백히 아닌 단어 (매칭 제외)
EXCLUSIONS = {
    "테스트", "프로세스", "서비스", "비스킷",
    "진행", "설명", "회사",
}

# 엄격 모드 임계값
STRICT_THRESHOLD = 0.75


def normalize(text: str) -> str:
    """정규화: 소문자, 구두점 제거, 공백 정리."""
    if not text:
        return ""
    text = text.lower().strip()
    # 구두점 제거
    text = re.sub(r"[,.!?~\-·、。！？\"'()（）\[\]]", "", text)
    # 공백 제거
    text = re.sub(r"\s+", "", text)
    return text


def is_wake_word_strict(text: str, threshold: float = STRICT_THRESHOLD) -> bool:
    """엄격 웨이크워드 매칭.

    조건:
    1. 너무 긴 텍스트 (>30자) 거부 (TV 대화 방지)
    2. 명백한 제외 단어 포함 시 거부
    3. primary 변형은 바로 인정
    4. secondary 변형 + 유사도 체크
    5. 짧은 발화 우대 (웨이크워드만 말했을 가능성)
    """
    if not text or not text.strip():
        return False

    original = text.strip()
    clean = normalize(text)

    # 1. 너무 긴 발화 차단 (TV 대화 방지)
    if len(original) > 30:
        return False

    # 2. 제외 단어 체크 (원본 기준)
    for exc in EXCLUSIONS:
        if exc in original:
            return False

    # 3. Primary 직접 매칭
    for v in PRIMARY_VARIANTS:
        if v in clean:
            # 짧은 발화일수록 확실함
            if len(clean) <= len(v) + 5:
                logger.info(f"Primary WAKE: '{original}' (clean='{clean}')")
                return True
            # 긴 발화인 경우 독립성 체크 (단어 경계)
            # 예: "데비스야" OK, "프로세스데비스부터" NG
            if re.search(rf"(^|[\s,.!?]){re.escape(v)}([\s,.!?야이]|$)", clean):
                logger.info(f"Primary WAKE (boundary): '{original}'")
                return True

    # 4. Secondary + 유사도 체크
    for v in SECONDARY_VARIANTS:
        if v in clean:
            # 짧은 발화만 인정
            if len(clean) <= 12:
                # 전체 문자열 유사도 체크
                sim = SequenceMatcher(None, "데비스", clean).ratio()
                if sim >= 0.5:
                    logger.info(f"Secondary WAKE: '{original}' sim={sim:.2f}")
                    return True

    # 5. 유사도 기반 (짧은 발화만, 엄격)
    if len(clean) <= 8:
        # 전체 비교
        sim_full = SequenceMatcher(None, "데비스", clean).ratio()
        if sim_full >= 0.65:
            logger.info(f"Full similarity WAKE: '{original}' sim={sim_full:.2f}")
            return True
        # 윈도우 비교
        for i in range(max(1, len(clean) - 3 + 1)):
            window = clean[i:i + 3]
            if len(window) >= 2:
                sim = SequenceMatcher(None, "데비스", window).ratio()
                if sim >= threshold:
                    logger.info(f"Similarity WAKE: '{original}' window='{window}' sim={sim:.2f}")
                    return True

    return False


def extract_command_after_wake(text: str) -> Optional[str]:
    """'데비스, [명령]' 형식에서 명령어만 추출.

    Returns:
        명령어 부분 (없으면 None → 별도 listen 필요)
    """
    if not text:
        return None

    # 웨이크워드 이후 텍스트 찾기
    patterns = [
        r"데비스[,\s]+(.+)",
        r"데뷔스[,\s]+(.+)",
        r"대비스[,\s]+(.+)",
        r"davis[,\s]+(.+)",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            cmd = m.group(1).strip()
            if len(cmd) >= 3:
                return cmd

    return None


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    print("=" * 60)
    print("웨이크워드 엄격 매칭 테스트")
    print("=" * 60)

    tests = [
        # (입력, 예상 결과)
        ("데비스", True),
        ("데비스!", True),
        ("데비스야", True),
        ("데비스 안녕", True),
        ("데비스, 오늘 뭐해", True),
        ("데비수", True),
        ("데빗", True),
        ("대비스 불러봐", True),
        ("davis", True),
        # 거부되어야 함
        ("안녕하세요", False),
        ("테스트 중입니다", False),
        ("프로세스 확인", False),
        ("서비스 점검", False),
        ("비스킷 먹고싶어", False),
        ("이것은 매우 긴 문장으로 데비스가 들어가도 TV 대화일 가능성이 높습니다", False),  # 너무 김
        ("좋은 하루 되세요", False),
        ("음", False),
        ("네", False),
        ("", False),
    ]

    passed = failed = 0
    for text, expected in tests:
        result = is_wake_word_strict(text)
        status = "PASS" if result == expected else "FAIL"
        if result == expected:
            passed += 1
        else:
            failed += 1
        print(f"  [{status}] '{text}' -> {result} (expected={expected})")

    print(f"\n결과: {passed} PASS / {failed} FAIL")

    print("\n=== 명령어 추출 테스트 ===")
    extract_tests = [
        "데비스 오늘 날씨 어때",
        "데비스, 이메일 확인해줘",
        "데비스",
        "그냥 하는 말이야",
    ]
    for t in extract_tests:
        cmd = extract_command_after_wake(t)
        print(f"  '{t}' -> cmd={repr(cmd)}")
