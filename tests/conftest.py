"""Shared pytest fixtures.

Loads `.env` once for the test session so tests that opt into `requires_api`
have credentials available without each test reaching for `os.environ`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(PROJECT_ROOT / ".env")


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def fake_env(monkeypatch: pytest.MonkeyPatch):
    """Inject deterministic env vars for tests that read os.environ."""

    def _set(**values: str) -> None:
        for k, v in values.items():
            monkeypatch.setenv(k, v)

    return _set
