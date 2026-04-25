# 폴더 정리 규칙 (Project Structure)

> 작성: 2026-04-26
> 적용 대상: `c:\Users\infow\cowork\jarvis project\`
> 이 문서는 폴더/파일을 어디에, 왜 두는지 결정하는 단일 기준이다.
> 의문이 생기면 코드를 옮기기 전에 이 문서를 먼저 갱신한다.

---

## 1. 디렉터리 트리 (목표 상태)

```
jarvis project/
├── CLAUDE.md                  # AI 개발자(Claude Code)용 지침
├── README.md                  # 사람이 읽는 프로젝트 소개·실행법
├── .env                       # 비밀 (gitignored)
├── .env.example               # 비밀 키 템플릿 (추적됨)
├── .gitignore
├── pyproject.toml             # 패키지 메타 + 도구(pytest, ruff) 설정
├── requirements.txt           # 활성 버전 런타임 의존성
├── requirements-dev.txt       # 개발/테스트 의존성
│
├── docs/                      # 모든 문서의 단일 소스
│   ├── PROJECT_STRUCTURE.md   # ★ 이 문서
│   ├── VERSIONING.md          # 버전 분기·승격·아카이빙 규칙
│   ├── DEVELOPMENT.md         # 로컬 개발 환경 구축 가이드
│   ├── ARCHITECTURE.md        # 활성 버전의 시스템 구조
│   └── archive/               # 옛 설계 문서 (.docx, 옛 README)
│
├── jarvis_v5/                 # ★ 활성(active) 버전 — 단 하나만 활성
│   ├── jarvis.py              # 진입점
│   ├── memory.py
│   ├── wake_matcher.py
│   ├── ...
│   └── README.md              # 이 버전 한정 빌드/실행 노트
│
├── archive/                   # 비활성 구버전 — 참고/롤백용, 빌드 대상 아님
│   ├── README.md              # 무엇을 왜 보관하는지
│   ├── v3_jarvis_cc/          # 옛 jarvis_cc/
│   └── v4_jarvis_agent/       # 옛 jarvis_agent.py + livekit-server/
│
├── scripts/                   # 빌드·설치·운영 스크립트
│   ├── install.bat
│   ├── build.bat
│   ├── uninstall.bat
│   └── start_jarvis.bat
│
├── tests/                     # pytest 단위·통합 테스트
│   ├── conftest.py
│   ├── unit/
│   └── integration/
│
├── reference_repos/           # 외부 오픈소스 클론 (gitignored)
├── reference_v6/              # 차기 v6 설계 레퍼런스 (gitignored)
└── livekit-server/            # 외부 바이너리 (gitignored)
```

---

## 2. 폴더별 정의와 진입 기준

| 폴더 | 들어가는 것 | 들어가면 안 되는 것 |
|---|---|---|
| **루트** | 프로젝트 전체에 영향을 주는 메타 파일(README, .env.example, requirements*.txt, pyproject.toml, .gitignore, CLAUDE.md). | 일회성 실험 스크립트, 특정 버전 전용 코드, 비밀 평문, 대용량 로그. |
| **docs/** | Markdown 문서 전체. 운영 가이드·설계 노트·아키텍처 다이어그램. | 코드, 비밀, 바이너리. .docx 같은 옛 설계는 `docs/archive/`로. |
| **jarvis_v5/** (활성) | 현재 빌드·실행 대상 코드. 진입점, 모듈, 그 버전 전용 README. | 폐기된 실험 모듈. 다른 버전의 코드. |
| **archive/** | 더 이상 빌드되지 않지만 참고가치가 남은 옛 버전 전체 트리. | 활성 버전이 import하는 코드 (그건 활성 트리로 옮겨야 함). |
| **scripts/** | OS 셸·배치 스크립트, CI 보조 스크립트. | Python 모듈 (그건 코드 트리로). |
| **tests/** | pytest 테스트와 fixture. `unit/`은 단일 모듈, `integration/`은 외부 의존(API·디바이스)이 필요한 것. | 프로덕션 코드. |
| **reference_repos/, reference_v6/, livekit-server/** | 외부 출처 자료. **모두 gitignored.** | 직접 수정한 코드 (수정해야 한다면 활성 트리에 fork). |

---

## 3. 파일 명명 규칙

- 파이썬 모듈: `snake_case.py`. 한 모듈에 한 가지 책임.
- 진입점은 패키지 루트의 `jarvis.py` 또는 `__main__.py` 하나로만 유지. 여러 진입점을 두지 않는다.
- 배치 스크립트: `동사_대상.bat` (예: `start_jarvis.bat`, `build_release.bat`). 모두 `scripts/`에 둔다.
- 테스트 파일: `test_<대상모듈명>.py`. 픽스처는 `conftest.py`.
- 문서: `UPPER_SNAKE.md` (예: `PROJECT_STRUCTURE.md`). 인덱스 성격이면 `README.md`.
- 한국어 파일명은 **루트와 활성 트리에서는 금지**. `docs/archive/` 같은 비활성 영역에서는 허용.

---

## 4. 비밀(secret) 처리 규칙

1. 비밀은 오직 `.env`에만. 코드에는 절대 평문으로 두지 않는다.
2. `.env`는 항상 gitignored. 추가될 가능성이 있는 키는 `.env.example`에 더미 값으로 등재.
3. `*.txt` 형태로 키를 보관하지 않는다. 발견되는 즉시 `.env`로 이주하고 원본 평문 파일은 삭제(루트의 `jarvis_Claude API.txt`, `open AI key.txt`가 현 시점 정리 대상).
4. 코드에서는 `os.environ.get("KEY")` 또는 `python-dotenv`로만 읽는다.
5. 로그/콘솔 출력에 키가 새지 않도록 환경변수 이름만 출력한다 (예: `loaded ANTHROPIC_API_KEY (len=…)`).

---

## 5. 버려지는 산출물(artifact) 처리

| 종류 | 위치 | gitignore | 보존 |
|---|---|---|---|
| `__pycache__/`, `*.pyc` | 자동 생성 | 예 | 무시 |
| `*.log` (런타임 로그) | 루트 또는 `logs/` | 예 | 7일치 로컬, CI는 아티팩트 |
| 임시 오디오 (`*.wav`, `*.mp3`, `*.tmp`) | OS temp 디렉터리 | 예 | 사용 후 즉시 정리 |
| 빌드 산출물 (`build/`, `dist/`) | 자동 생성 | 예 | 릴리스 시에만 보존 |
| 모델 캐시 (faster-whisper, silero) | OS 사용자 캐시 | 예 | 무시 |

루트에 1MB 넘는 로그 파일이 추적되는 일이 없도록 한다 (현 시점 `realtimesst.log`는 정리 대상).

---

## 6. 새 파일을 만들 때 체크리스트

1. **이 파일이 활성 버전인가, 옛 버전인가?** → 활성이면 `jarvis_v5/`, 옛 버전이면 `archive/...`. 결정이 안 서면 만들지 않는다.
2. **테스트 가능한 단위인가?** → 그렇다면 `tests/unit/test_<이름>.py`도 같이 추가.
3. **외부 의존이 새로 생기는가?** → `requirements.txt` (런타임) 또는 `requirements-dev.txt` (개발만)에 즉시 등재. 버전 핀 명시.
4. **비밀이 들어가는가?** → 코드에는 절대 안 됨. `.env.example`에 키 이름만 추가.
5. **배치/셸 스크립트인가?** → `scripts/`에. 루트에 두지 않는다.
6. **문서인가?** → `docs/`에. 루트의 `README.md`는 “프로젝트 소개”에 한정, 운영 디테일은 `docs/`로.

---

## 7. 위반 사례 청산 목록 (현 시점, 2026-04-26)

| 위반 | 위치 | 처리 |
|---|---|---|
| 비밀 평문 | `jarvis_Claude API.txt`, `open AI key.txt` | `.env`로 이주 후 삭제 |
| 한국어 파일명, 옛 설계 | `JARVIS-CC_v3_최종계획서.docx`, `JARVIS-CC_참조소스코드.md` | `docs/archive/`로 이동 |
| 옛 버전 코드 | `jarvis_cc/`, `jarvis_agent.py`, `livekit-server/`, `start_jarvis_v4.bat` | `archive/v3_jarvis_cc/`, `archive/v4_jarvis_agent/`로 이동 |
| 배치 스크립트 산재 | 루트의 `*.bat` | `scripts/`로 이동 |
| 대용량 로그 추적 | `realtimesst.log` | 삭제, gitignore 강화 |
| `mpv/` 더미 | `mpv/mpv.zip` (9 bytes) | 삭제 또는 실제 바이너리로 교체 |
| 진입점 중복 | v3 main, v4 jarvis_agent, v5 jarvis 공존 | v5만 활성, 나머지는 archive |

청산은 **VERSIONING.md의 마이그레이션 절차**를 따라 단계별로 수행한다.
