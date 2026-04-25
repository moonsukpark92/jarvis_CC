# 개발 환경 가이드 (Development)

> 작성: 2026-04-26
> 대상: 활성 버전 v5 (DAVIS, `jarvis_v5/`).
> 사전 지식: Python, Windows 10/11.

---

## 1. 설치 (Setup)

### 1.1 사전 요구사항

- Windows 10/11
- Python 3.11+ (3.12 권장, 3.13 미지원 라이브러리 있음)
- Git
- 마이크/스피커 (헤드셋 권장 — 에코 취소)
- 인터넷 (Anthropic API, edge-tts CDN 필요)

### 1.2 첫 설정

```bat
:: 1) 저장소 클론
git clone <repo> jarvis-project
cd jarvis-project

:: 2) 가상환경
python -m venv .venv
.venv\Scripts\activate

:: 3) 런타임 의존성
pip install -r requirements.txt

:: 4) 개발 의존성
pip install -r requirements-dev.txt

:: 5) 비밀 키 설정
copy .env.example .env
notepad .env       :: 실제 키 채워넣기

:: 6) 사전 검증
pytest -q
python -m jarvis_v5.jarvis --help
```

`pytest`가 통과하지 않으면 코드 작업을 시작하지 않는다.

---

## 2. 디렉터리 안내 (요약)

자세한 규칙은 [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md). 빠른 안내만:

- 활성 코드: `jarvis_v5/`
- 옛 버전: `archive/`
- 문서: `docs/`
- 테스트: `tests/`
- 스크립트: `scripts/`

---

## 3. 일상 워크플로우

```bat
:: 작업 시작
git pull
.venv\Scripts\activate
git checkout -b feat/<짧은-이름>

:: 코드 변경 후
pytest tests/unit -q
pytest tests/integration -q -m "not requires_audio"  :: CI 모드

:: 린트
ruff check jarvis_v5 tests

:: 커밋
git add .
git commit -m "feat: 한 줄 요약"

:: PR 또는 main 머지
git checkout main
git merge --no-ff feat/<짧은-이름>
```

커밋 메시지는 Conventional Commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.

---

## 4. 실행

### 4.1 활성 버전 (v5)

```bat
.venv\Scripts\activate
python -m jarvis_v5.jarvis
```

또는 `scripts\start_jarvis.bat`.

### 4.2 옛 버전 롤백 (필요 시)

`archive/v3_jarvis_cc/README.md` 또는 `archive/v4_jarvis_agent/README.md` 참조. 기본적으로 별도 가상환경을 권장한다 (의존성 충돌).

---

## 5. 테스트 정책

- **단위(unit)**: 외부 의존 없이 빠르게 (밀리초~초). `tests/unit/` 아래.
- **통합(integration)**: 마이크/스피커/네트워크 필요. `tests/integration/`. pytest 마커로 분리:
  - `@pytest.mark.requires_audio` — 마이크/스피커 필요
  - `@pytest.mark.requires_api` — Anthropic API 키 필요
  - `@pytest.mark.slow` — 5초 이상 걸리는 것
- 기본 `pytest`는 `requires_audio`를 제외한다 (`pyproject.toml`의 `addopts` 참조).
- 새 코드는 단위 테스트와 함께 머지한다. 통합 테스트는 가능한 만큼.
- 테스트는 절대 실제 API 키를 평문으로 갖지 않는다. `monkeypatch`로 환경변수 주입.

---

## 6. 코드 스타일

- 포매터: `ruff format`. 실행 전에 한 번씩.
- 린터: `ruff check`. 경고 0을 목표로.
- 타입 힌트: 모든 public 함수에 권장. `mypy`는 점진 도입.
- import 순서: stdlib → 서드파티 → 로컬. ruff isort에 맡긴다.
- 한국어 식별자/한국어 docstring 금지. 한국어는 사용자 표시 문자열에서만.
- 주석은 “왜”에 한정. “무엇”은 코드가 말하게.

---

## 7. 비밀(Secret) 처리

- 키는 `.env`에만. 코드/주석/로그에 절대 평문으로 두지 않는다.
- 새 키가 필요하면 `.env.example`에 더미 값으로 등재 후 PR.
- API 키 노출이 의심되면 즉시 발급처에서 회전(rotate)하고, git 히스토리에 들어갔는지 `git log -p -- .env*` 등으로 확인.

---

## 8. 로깅

- `logging` 모듈만 사용. `print`는 디버깅 외 금지.
- 로그 파일은 OS temp 또는 `%LOCALAPPDATA%\jarvis\logs\`. **저장소 안에 쓰지 않는다.**
- 사용자 발화·응답을 로그에 남길 때는 INFO가 아닌 DEBUG로, 별도 파일로 분리.
- 비밀은 절대 로그에 들어가지 않게 (`logging.Filter`로 마스킹).

---

## 9. 마이그레이션 (v3/v4 잔재 청소) — 1회성 절차

루트 작업 디렉터리에서 (Bash 셸 기준):

```bash
# 0) 작업 브랜치
git checkout -b migrate/consolidate-to-v5

# 1) v5를 추적 대상에 추가
git add jarvis_v5/

# 2) archive 골격
mkdir -p archive/v3_jarvis_cc archive/v4_jarvis_agent docs/archive

# 3) v3 이동
git mv jarvis_cc/* archive/v3_jarvis_cc/
git mv JARVIS-CC_v3_최종계획서.docx docs/archive/
git mv JARVIS-CC_참조소스코드.md docs/archive/

# 4) v4 이동 (livekit-server는 gitignored, 폴더만 OS 단위로 이동)
git mv jarvis_agent.py archive/v4_jarvis_agent/
git mv start_jarvis_v4.bat archive/v4_jarvis_agent/
mv livekit-server archive/v4_jarvis_agent/

# 5) 스크립트 이동
mkdir -p scripts
git mv install.bat build.bat uninstall.bat scripts/

# 6) 평문 키 제거 (이미 .env 옮긴 후)
rm "jarvis_Claude API.txt" "open AI key.txt"

# 7) 대용량 로그 제거
rm -f realtimesst.log

# 8) mpv 더미 제거
rm -rf mpv/

# 9) requirements를 v5 기준으로 재생성
# (jarvis_v5의 import를 토대로 수동 작성 — DEVELOPMENT.md 11항 참조)

# 10) 한 커밋으로
git add -A
git commit -m "chore: consolidate to v5 as the single active version"
```

각 단계는 가역적이지 않다. 실행 전 `git status`로 작업트리가 깨끗한지 확인.

---

## 10. 문제 해결

| 증상 | 원인/해결 |
|---|---|
| `pyaudio` 빌드 실패 | `pip install pipwin && pipwin install pyaudio`. 또는 RealtimeSTT의 휠 사용. |
| `faster-whisper` 모델 다운로드 멈춤 | OS 사용자 캐시(`~/.cache/huggingface`) 권한/디스크 확인. |
| `edge-tts` 401/403 | Microsoft가 토큰 형식을 바꾼 경우. `pip install -U edge-tts`. |
| Windows 마이크가 잡히지 않음 | 설정 → 개인정보 → 마이크 → 데스크톱 앱 허용. |
| 콘솔 한글 깨짐 | `chcp 65001` 후 실행, 또는 진입점 상단의 UTF-8 보정 코드 유지. |

---

## 11. requirements.txt 재구성 가이드

활성 버전 기준 의존성은 import에서 역추적한다. 출발점:

```bash
# jarvis_v5에서 import되는 외부 모듈 추출
grep -rhE "^(import|from) " jarvis_v5/ | grep -v "^from \." | sort -u
```

이 목록에서 stdlib(asyncio, threading, …)을 제외하고, 각각 PyPI 패키지명으로 매핑하여 핀(`==X.Y.Z`)을 명시한다. 임시 점검 후 `pip freeze | grep -iE "anthropic|edge-tts|RealtimeSTT|..."` 결과로 정확한 버전을 확정한다.
