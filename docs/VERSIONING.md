# 버전 관리 규칙 (Versioning & Branching)

> 작성: 2026-04-26
> 핵심 원칙: **활성(active)은 단 하나. 다른 버전은 `archive/` 또는 git 브랜치에만 존재한다.**

---

## 1. 버전 정책 한 문장 요약

> 메이저 버전은 폴더(`jarvis_v5/`)로 분리한다. 활성 버전은 항상 정확히 하나만 존재하며, 그 외 모든 메이저 버전은 `archive/`로 옮기거나 별도 git 브랜치로만 보존한다.

---

## 2. 메이저 버전(Major) 정의

새 메이저 버전은 다음 중 하나라도 해당하면 시작한다.

- 런타임 아키텍처가 바뀐다 (예: 상태머신 → RealtimeSTT 스트리밍 → LiveKit Agents).
- 핵심 의존성이 비호환적으로 바뀐다 (예: `pyaudio` → `RealtimeSTT`, `pygame` → `mpv`).
- 진입점/실행 방식이 바뀌어 사용자 명령이 달라진다.
- 외부 인터페이스(설정 파일 스키마, 키 이름)가 호환되지 않는다.

폴더 이름은 `jarvis_v<숫자>/` 패턴. 의미상 명확한 닉네임이 있으면 README에 부기하되 폴더명에는 숫자만 쓴다.

---

## 3. 현재 버전 레지스트리

| 코드 | 폴더 | 상태 | 진입점 | 핵심 스택 | 비고 |
|---|---|---|---|---|---|
| **v3** (JARVIS-CC) | `archive/v3_jarvis_cc/` (이전 예정) | 아카이브 | `main.py` | openwakeword + faster-whisper + edge-tts + worker pool | 안정성 좋음. 롤백 후보. |
| **v4** (LiveKit) | `archive/v4_jarvis_agent/` (이전 예정) | 아카이브 | `jarvis_agent.py` | LiveKit Agents + Silero + OpenAI STT/TTS + Anthropic | 실험. WebRTC UI. |
| **v5** (DAVIS) | `jarvis_v5/` | **활성** | `jarvis.py` | RealtimeSTT + Anthropic streaming + edge-tts | sub-1.5s 응답 목표. |
| v6 (계획) | `reference_v6/` (gitignored 레퍼런스만) | 설계 단계 | — | AutoGPT/Letta/mem0 등 검토 중 | 코드 미생성. |

활성 버전이 바뀔 때마다 이 표를 갱신한다 (그것이 변경의 단일 진실 공급원이다).

---

## 4. 마이너/패치 — 같은 메이저 안에서

같은 메이저 안의 변경은 폴더를 분리하지 않는다. 다음으로 추적한다.

- **git 커밋**: Conventional Commits 권장. `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
- **태그**: 의미 있는 마일스톤에 `v5.1.0` 형태 태그.
- **CHANGELOG**: 활성 버전 폴더의 `README.md` 하단 또는 `docs/CHANGELOG.md`에 누적.

마이너 버전 분기를 위해 폴더를 복제하지 않는다. 분기가 필요하면 git 브랜치를 쓴다.

---

## 5. 메이저 승격(Promotion) 절차

새 버전(예: v6)이 다음을 모두 충족했을 때만 활성 승격.

1. 모든 P0 기능이 동작하고, P0 통합 테스트가 통과한다.
2. README와 `requirements.txt`가 새 버전 기준으로 갱신되었다.
3. `.env.example`이 새 버전 키 셋과 일치한다.
4. 옛 활성 버전을 `archive/v<n>_<이름>/`으로 무손실 이동했고, 그 안에 자체 README가 있다.
5. `docs/VERSIONING.md`(이 문서)의 레지스트리 표가 갱신되었다.
6. CLAUDE.md의 “활성 버전 진입점” 섹션이 갱신되었다.

위 6개를 한 PR/커밋에 묶어서 처리한다. 부분적으로 승격된 상태로 main에 머무르지 않는다.

---

## 6. 아카이빙 규칙

- 아카이빙 시점에 폴더를 그대로 옮긴다 (`mv jarvis_cc archive/v3_jarvis_cc`). 코드를 수정하지 않는다.
- `archive/v?_*/README.md`에 다음 4가지를 적는다:
  1. 마지막 활성 날짜
  2. 왜 아카이빙되었는지 (한 단락)
  3. 어떤 의존성/외부 자원이 필요한지
  4. 어떻게 다시 띄울 수 있는지 (롤백 절차)
- 아카이브된 코드는 **CI/빌드 대상에서 제외**한다 (pytest 컬렉션 제외, PyInstaller 진입점 제거).
- 6개월 이상 참조되지 않은 아카이브는 git 태그(`archived/v3-final`)만 남기고 폴더를 삭제할 수 있다. 단, 삭제 PR에 그 결정을 명시한다.

---

## 7. 브랜치 전략

소규모 1인 개발이 전제이므로 단순화한다.

- `main`: 항상 활성 버전이 동작 가능한 상태.
- `feat/<짧은-이름>`: 메이저 버전 안의 기능 작업.
- `migrate/v<n>-to-v<n+1>`: 다음 메이저로의 이행 작업. 승격 PR이 끝나면 머지 후 삭제.
- `experiment/<이름>`: 실패해도 무방한 탐색. main 머지 금지, 1주일 안에 결론.

force-push는 본인 브랜치에서만. main은 절대 force-push 금지.

---

## 8. 의존성 버전 관리

- `requirements.txt`는 **활성 버전 기준**. 다른 버전을 위한 의존성은 적지 않는다.
- 핀 정책: `package==X.Y.Z` (정확 핀). 보안 패치는 즉시 갱신.
- `requirements-dev.txt`는 pytest, ruff, mypy, pyinstaller 등 빌드/테스트 전용.
- 옛 버전 의존성은 `archive/v?_*/requirements.txt`에 격리.
- 새 의존성은 추가하기 전 다음을 확인:
  - 활성 버전 진입점에서 실제로 import 되는가?
  - 라이선스가 호환되는가? (MIT/Apache/BSD 외에는 README에 명시)
  - 마지막 릴리스가 12개월 안인가?

---

## 9. 설정 파일 호환성

- 활성 버전의 설정 스키마는 `docs/CONFIGURATION.md`에 명시.
- 키 이름은 메이저 버전 내에서 절대 바꾸지 않는다 (마이너 호환성).
- 메이저 승격 시 키 이름을 정리할 수 있다. 단, `archive/`의 옛 설정과 신 설정의 매핑 표를 마이그레이션 노트에 남긴다.

---

## 10. 현재 진행 중인 마이그레이션 (v3/v4 → v5)

상태: 미완. 다음 순서로 처리한다.

1. v5 활성 트리(`jarvis_v5/`)를 git에 add 한다 (현재 untracked 다수).
2. `requirements.txt`를 v5 기준으로 재작성한다 (현재는 v3 기준).
3. `archive/` 폴더 생성 후 `jarvis_cc/` → `archive/v3_jarvis_cc/`, `jarvis_agent.py`+`livekit-server/`+`start_jarvis_v4.bat` → `archive/v4_jarvis_agent/`로 이동한다.
4. 각 archive 폴더에 README.md 작성 (위 6항).
5. 루트 평문 키(`jarvis_Claude API.txt`, `open AI key.txt`)를 `.env`로 이주 후 삭제.
6. `realtimesst.log` 삭제, `.gitignore` 보강.
7. 루트 `README.md`를 v5 진입점 기준으로 갱신.
8. 한 커밋으로 묶어서 “chore: consolidate to v5 as active version” 머지.

이 시퀀스는 `docs/DEVELOPMENT.md`의 마이그레이션 섹션에서 명령어 단위로 안내한다.
