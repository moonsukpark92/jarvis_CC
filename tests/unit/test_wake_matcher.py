"""Smoke tests for jarvis_v5/wake_matcher.py.

These run without audio devices or API keys, so they are part of the
default pytest run.
"""
from __future__ import annotations

import sys
from pathlib import Path

V5 = Path(__file__).resolve().parents[2] / "jarvis_v5"
sys.path.insert(0, str(V5))

from wake_matcher import (  # noqa: E402
    extract_command_after_wake,
    is_wake_word_strict,
)


def test_strict_match_recognizes_canonical_form():
    assert is_wake_word_strict("데비스")


def test_strict_match_rejects_obvious_negative():
    assert not is_wake_word_strict("안녕하세요 오늘 날씨 어때")


def test_extract_command_returns_remainder():
    text = "데비스, 오늘 일정 알려줘"
    rest = extract_command_after_wake(text)
    assert rest is not None
    assert "일정" in rest
