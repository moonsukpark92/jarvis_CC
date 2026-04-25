# DAVIS 음성 어시스턴트 - 오픈소스 레퍼런스 분석 노트

> 분석 대상: reference_v6/ 폴더의 5개 레포 (shallow clone)
> 작성일: 2026-04-21
> 목적: DAVIS v6 설계에 적용할 패턴 도출

---

## 1. Letta (MemGPT) — letta-ai/letta

**핵심 아키텍처**
- "MemGPT" 패러다임: LLM 컨텍스트 윈도우를 OS의 RAM처럼 다루고, 디스크(아카이브)와 RAM(코어 메모리) 사이를 LLM이 직접 도구 호출로 페이징한다.
- `letta/agents/` 에 `voice_agent.py`, `voice_sleeptime_agent.py` 등 음성 전용 에이전트 분리 — 저지연 스트리밍 루프와 백그라운드 요약 에이전트가 별도.

**메모리 메커니즘**
- 4계층: `core_memory`(블록) + `recall_memory`(최근 대화) + `archival_memory`(벡터 DB) + `summary_memory`(요약).
- `ContextWindowOverview` 스키마(`schemas/memory.py`)가 토큰별 카운팅 — 시스템/코어/요약/디렉토리/툴룰을 명시적으로 분리.
- `Summarizer` 서비스가 한도 초과 시 자동 요약 후 archival로 이관.

**DAVIS 적용 포인트**
- **VoiceAgent + SleeptimeAgent 분리 패턴**: 사용자 응답은 빠른 스트리밍 루프, 메모리 정리는 유휴(sleeptime) 시간에 별도 에이전트로 처리. DAVIS도 TTS 응답 중에는 메모리 갱신 작업을 미루고, 침묵 구간에 백그라운드 요약·이관을 돌리면 체감 지연이 줄어든다.
- 코어 메모리 "블록(Block)" 구조 — 사용자 페르소나/상황/현재 작업을 분리 저장.

---

## 2. mem0 — mem0ai/mem0

**핵심 아키텍처**
- "메모리 추출 → 저장 → 검색" 파이프라인 라이브러리. 대화에서 LLM이 사실(fact)을 추출하고, 임베딩+벡터스토어+SQLite(history)에 저장.
- `Memory.add()` / `search()` / `update()` 4-CRUD 단순 API.

**메모리 메커니즘**
- `ADDITIVE_EXTRACTION_PROMPT`로 새 메시지에서 fact만 추출 → 기존 메모리와 LLM 비교 후 ADD/UPDATE/DELETE/NOOP 결정 (자가 정리).
- BM25 + 벡터 유사도 + 엔티티 부스팅 하이브리드 점수 (`utils/scoring.py`).
- `procedural_memory`(프로시저), `entity extraction`까지 분리.

**DAVIS 적용 포인트**
- **사실 추출 + 자가 갱신 루프**: 매 대화 후 "이 발화에서 새로 알게 된 사실이 있나?" LLM 판정 → 기존 메모리와 충돌 시 UPDATE. DAVIS의 사용자 선호(예: 좋아하는 음악, 통근 시간)를 누적하기 좋다.
- BM25+벡터 하이브리드 검색이 한국어 키워드(이름, 날짜)에 유리.

---

## 3. Open Interpreter — OpenInterpreter/open-interpreter

**핵심 아키텍처**
- 단일 클래스 `OpenInterpreter`가 "LLM ↔ Computer" 왕복 루프. `respond.py`가 generator로 토큰 단위 yield.
- LMC(Language Model Computer) 메시지 포맷 — role/type/format/content 4-필드로 코드/출력/마크다운 통합.

**작업 실행 (Task Execution)**
- `auto_run` 플래그 + `loop_breakers`(`"The task is done."` 등 종결 문구) 감지로 자율 루프 종료.
- `computer_use/loop.py`의 Anthropic computer-use 구현 — 스크린샷 → 클릭/타이핑 도구 호출.
- `core/computer/` 안에 OS, browser, files, terminal 등 모듈식 능력 분리.

**DAVIS 적용 포인트**
- **loop_breakers 종결 패턴**: "The task is done." 같은 약속된 종결 문자열로 음성 멀티턴 종료 판정. DAVIS는 "끝났습니다" / "더 필요한 거 있으세요?" 등을 종결 토큰으로 등록.
- LMC 메시지 포맷 — DAVIS의 STT/LLM/TTS/도구 결과를 단일 스키마로 통합 추적.

---

## 4. AutoGPT — Significant-Gravitas/AutoGPT

**핵심 아키텍처**
- `forge` 프레임워크 기반 컴포넌트 조합형 에이전트. `BaseAgent` + 프로토콜(`MessageProvider`, `CommandProvider`, `AfterExecute` 등)을 구현하는 컴포넌트들이 플러그인 식으로 결합.
- `agents/agent.py`에 `ActionHistoryComponent`, `FileManager`, `Web`, `Clipboard`, `Watchdog`, `Todo`, `UserInteraction` 등 20+ 컴포넌트 등록.

**작업 계획 접근**
- `prompt_strategies/`에 **6가지 전략**: `one_shot`, `plan_execute`, `lats`(Tree-search), `multi_agent_debate`, `reflexion`, `rewoo`, `tree_of_thoughts` — 같은 LLM에 다른 프롬프트 전략을 갈아끼움.
- `EpisodicActionHistory`로 행위→결과를 에피소드로 기록, 다음 스텝 프롬프트에 주입.

**DAVIS 적용 포인트**
- **프로토콜 기반 컴포넌트 구조**: DAVIS도 `WakewordProvider`, `STTProvider`, `ToolProvider`, `AfterTurnHook` 같은 프로토콜로 분해하면 신규 도구(스마트홈, 일정) 추가 시 코어 수정 불필요.
- **Reflexion / Plan-Execute 프롬프트 전략 토글** — 단순 명령은 `one_shot`, 복합 요청("내일 출장 준비해줘")은 `plan_execute`로 자동 분기.

---

## 5. TaskWeaver — microsoft/TaskWeaver

**핵심 아키텍처**
- "Planner ↔ Worker(Roles)" 멀티-롤 구조. `Planner`가 사용자 요청을 받아 worker(`code_interpreter`, `plugin` 등)에게 위임, 결과를 다시 받아 사용자에게 응답.
- `JSON 스키마 강제 응답` — Planner는 `response_json_schema`로 `send_to`/`message`/`thought` 필드 보장.

**작업 분해 (Task Decomposition)**
- `Round`(라운드) → `Post`(메시지) 단위로 메모리 누적. `RoundCompressor`가 옛 라운드를 압축.
- `ExperienceGenerator` — 과거 세션에서 학습한 "경험"을 yaml로 저장 후 다음 계획에 주입(few-shot).
- `Attachment` 시스템 — 코드/플랜/사고를 메시지에 첨부 메타로 분리.

**DAVIS 적용 포인트**
- **Planner-Worker 분리 + JSON 스키마 응답**: DAVIS의 LLM 출력을 `{intent, slot, reply, route_to}` JSON으로 강제하면 STT 오인식에도 라우팅이 안정적.
- **ExperienceGenerator 패턴**: 사용자별 "성공한 명령 시퀀스"를 `experience.yaml`로 저장 → 새 세션 시작 시 시스템 프롬프트에 주입해 개인화.
- `RoundCompressor`로 음성 대화의 긴 라운드를 압축 — DAVIS의 음성 세션이 길어질 때 핵심.

---

## 종합 — DAVIS v6 우선순위 적용안

1. **메모리 4계층 (Letta)**: `core_block`(사용자 프로필) / `recall`(현재 대화) / `archive`(벡터) / `summary`. 각 계층 토큰 한도 명시.
2. **사실 추출 자가-갱신 (mem0)**: 매 턴 종료 후 ADD/UPDATE/DELETE 판정 LLM 호출 — sleeptime에 비동기 실행.
3. **Sleeptime 분리 (Letta)**: 응답 스트리밍 루프와 메모리/요약 루프를 asyncio task로 분리 — 음성 지연 최소화.
4. **컴포넌트 프로토콜 (AutoGPT)**: `Provider`/`Hook` 인터페이스로 도구 플러그인화.
5. **JSON 스키마 강제 라우팅 (TaskWeaver)**: LLM 출력을 의도/슬롯/응답으로 강제 → STT 오류 내성.
6. **loop_breakers 종결 (Open Interpreter)**: 음성 멀티턴 자동 종료 문구 등록.

> 다음 액션: `jarvis_v5/jarvis.py`에 위 1·3·6번부터 점진 적용 (메모리 계층 분리 + sleeptime task + 종결어 감지).
