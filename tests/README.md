# Tests

```
tests/
├── conftest.py        # shared fixtures, .env loading
├── unit/              # fast, no external deps
└── integration/       # opt-in: audio device / API credentials
```

## 실행

```bat
:: 기본 (단위 테스트만)
pytest

:: 통합까지
pytest -m "requires_audio or requires_api"

:: 특정 마커 제외
pytest -m "not slow"
```

## 마커

- `requires_audio` — 실제 마이크/스피커가 있어야 통과
- `requires_api` — Anthropic/Google/Telegram 키 필요
- `slow` — 2초 이상 걸리는 테스트

기본 실행에서는 모두 자동 제외됩니다 ([pyproject.toml](../pyproject.toml) `addopts` 참조).

## 새 테스트 추가 시

1. 단위 테스트면 `tests/unit/test_<모듈명>.py`.
2. 외부 의존이 있으면 `tests/integration/`에 두고 마커 부착.
3. API 키는 `monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")`로 주입. 절대 평문 키를 코드에 두지 않습니다.
4. `archive/`의 옛 버전 코드는 테스트하지 않습니다 (pytest collection에서 제외됨).
