# CLAUDE.md — AI 개발자(Claude Code) 작업 지침

이 문서는 Claude Code가 이 저장소에서 작업할 때 자동으로 읽히는 단일 진실 공급원이다.
사람용 소개는 [README.md](README.md), 상세 규칙은 [docs/](docs/).

---

## 1. 활성 버전 (단 하나)

- **활성**: `jarvis_v5/` (DAVIS — RealtimeSTT + Anthropic streaming + edge-tts)
- **진입점**: `python -m jarvis_v5.jarvis` (또는 `scripts/start_jarvis.bat`)
- **아카이브**: `archive/v3_jarvis_cc/`, `archive/v4_jarvis_agent/` — 빌드/수정 대상 아님

활성이 아닌 코드를 수정하라는 요청을 받으면, 먼저 “이건 archive 영역인데 정말 거기를 손대시겠어요?”라고 사용자에게 확인한다.

---

## 2. 작업 시작 전에 항상 확인

1. 어떤 폴더를 건드리는가? → [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)의 폴더 정의에 부합하는가.
2. 메이저 버전을 넘나드는가? → [docs/VERSIONING.md](docs/VERSIONING.md)의 승격/아카이빙 절차를 따른다.
3. 새 의존성을 추가하는가? → `requirements.txt`(런타임) 또는 `requirements-dev.txt`(개발)에 즉시 핀 명시.
4. 비밀이 등장하는가? → 코드/로그에 평문 금지. `.env` + `.env.example`만.
5. 테스트는 같이 갱신했는가? → 단위 테스트는 같은 PR에 포함.

---

## 3. 절대 금지

- 활성 버전과 옛 버전을 동시에 수정하는 PR을 만든다 (혼란의 근원).
- API 키, 토큰, 비밀번호를 코드/주석/로그/문서에 평문으로 둔다.
- `archive/` 안의 코드를 활성 버전이 import 한다 (필요하면 활성 트리로 옮긴다).
- `requirements.txt`에 옛 버전 전용 의존성을 섞어 넣는다.
- 한국어 파일명을 활성 트리에 만든다.
- main 브랜치에 force-push.
- 대용량 로그/오디오/모델 파일을 git에 추가.

---

## 4. 권장 작업 순서

1. 사용자 의도와 [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)·[docs/VERSIONING.md](docs/VERSIONING.md)를 대조.
2. 변경 범위가 작으면 바로 작업, 크면 한 줄로 계획 제시 후 승인받기.
3. 단위 테스트부터 (또는 같이) 작성.
4. `ruff check` + `pytest -q`가 통과하는지 확인 후 커밋.
5. Conventional Commits 메시지 (`feat:`, `fix:`, …) 사용.

---

## 5. 도메인 용어 (사용자 환경)

- 사용자: 박문석(박대표). 데코페이브 대표.
- 어시스턴트 호출명: “데비스”(DAVIS, v5의 웨이크워드).
- 관련 시스템: AIHUB(별도 프로젝트, 이 저장소와 무관), 문실장(별도 BOT, 이전 완료).

이 용어들은 코드 식별자가 아니라 STT/페르소나 프롬프트에서만 사용된다.

---

## 6. 문서 인덱스

| 목적 | 파일 |
|---|---|
| 폴더 정리 규칙 | [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) |
| 버전 관리 규칙 | [docs/VERSIONING.md](docs/VERSIONING.md) |
| 개발 환경 가이드 | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
| 사람용 소개 | [README.md](README.md) |
| v5 업그레이드 노트 | [jarvis_v5/jarvis_upgrade_notes.md](jarvis_v5/jarvis_upgrade_notes.md) |
