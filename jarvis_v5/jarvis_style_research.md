# JARVIS 스타일 대화형 AI 오픈소스 리서치 (DAVIS 참고용)

> 작성일: 2026-04-26 / 대상: `jarvis_v5` (DAVIS) — 자연 대화 + 인격 + 창의 + 데이터 기반 추론
> 목적: 아이언맨의 JARVIS처럼 "사람처럼 사고하지만 데이터에 충실한" 어시스턴트로 진화시키기 위한 오픈소스 패턴 수집.

---

## TOP 10 랭킹 (DAVIS 관점, 차용 가치 순)

| # | 프로젝트 | Stars | 핵심 차용 패턴 |
|---|---|---|---|
| 1 | **letta-ai/letta** (구 MemGPT) | ~17k | OS형 메모리 계층 (core/archival), `.af` 직렬화, 모델간 인격 이식 |
| 2 | **microsoft/autogen** | 50.4k | 다중 에이전트 대화 협업, role-based agent (분석가/창의가 분리) |
| 3 | **joaomdmoura/crewAI** | ~43k | role + goal + backstory 3종 인격 슬롯, 협업 워크플로 |
| 4 | **langchain-ai/langgraph** | ~8k | Stateful graph orchestration, reflection/critic 루프 |
| 5 | **microsoft/JARVIS (HuggingGPT)** | 24.1k | Plan→Select→Execute→Respond 4단계 파이프라인 |
| 6 | **Significant-Gravitas/AutoGPT** | ~183k | 목표→하위 태스크 자율 분해, self-evaluation |
| 7 | **leon-ai/leon** | ~17k | 프라이버시 우선 + 스킬 모듈 + 로컬 우선 어시스턴트 구조 |
| 8 | **SillyTavern/SillyTavern** | (대형) | Persona/Character card 분리, World Info(컨텍스트 주입) |
| 9 | **isair/jarvis** | (중형) | "3인칭처럼 자연 대화", 무한 MCP 도구, 컨텍스트 부패 방지 |
| 10 | **miltonian/principles** + **ailev/FPF** | (소형) | First-principles 분해, 감사 가능한 추론 기록 |

---

## 1. 인격(Personality) / 정체성 계층

### letta-ai/letta — https://github.com/letta-ai/letta
- **메모리 OS**: core memory(인격/사용자 프로필 항상 컨텍스트), recall memory(대화 이력), archival memory(장기 검색).
- **Agent File (.af)**: 인격 + 메모리 + 도구를 한 파일로 직렬화 → 모델(Claude/GPT/Gemini) 바꿔도 인격 유지.
- **DAVIS 차용**: 현재 `memory.py`를 letta 패턴(persona block + human block + 검색 가능한 archival)으로 재설계. "데비스는 박대표의 비서이며 데이터 우선이지만 농담을 좋아한다" 같은 코어 블록을 시스템 프롬프트와 분리.

### SillyTavern — https://github.com/SillyTavern/SillyTavern
- **Persona vs Character 분리**: 사용자(박대표) 페르소나와 어시스턴트(데비스) 캐릭터를 완전 분리.
- **World Info / Lorebook**: 트리거 키워드가 입력에 등장하면 관련 컨텍스트를 동적 삽입 (토큰 절약).
- **DAVIS 차용**: 데코페이브/AIHUB/ERP 도메인을 World Info 식 키워드 트리거로 구성하면 시스템 프롬프트가 비대해지지 않음.

---

## 2. 추론 스타일 (창의 ↔ 분석 균형)

### microsoft/autogen — https://github.com/microsoft/autogen
- **AssistantAgent + UserProxyAgent + 그룹채팅**: "Analyst" agent가 데이터 검증, "Creative" agent가 발산, 둘이 토론해서 최종안 도출.
- **DAVIS 차용**: 단일 LLM 호출 대신, 중요 의사결정은 내부에서 분석가/창의가 2-shot 토론 후 합성. `task_planner.py`를 다중 역할로 확장.

### crewAI — https://github.com/joaomdmoura/crewAI
- **Agent 정의 3요소**: `role`, `goal`, `backstory` → 자연스럽게 톤·관점·우선순위가 분기.
- **DAVIS 차용**: 데비스의 backstory를 명시적으로 작성 ("데코페이브 본사 IT실 출신으로 박대표를 7년째 보좌, MIT 데이터 사이언스 부심").

### miltonian/principles — https://github.com/miltonian/principles
- **First-principles 분해**: 목표 → 근본 가정 추출 → 최소 하위 태스크 → 검증 루프.
- **ailev/FPF** — https://github.com/ailev/FPF: bounded contexts + decision records + auditable reasoning.
- **DAVIS 차용**: "왜?" 질문 시 답하기 전 내부에서 (1) 가정 명시 (2) 가정 반박 (3) 데이터로 검증 — 3단 자기 비판 후 응답. JARVIS의 "근거 있는 자신감" 톤이 여기서 나옴.

### langgraph — https://github.com/langchain-ai/langgraph
- **Graph 기반 stateful 오케스트레이션**: reflection, critic, retry 노드를 명시적 엣지로.
- **DAVIS 차용**: "응답 생성 → 자체 critic(데이터 출처 있나?) → 부족하면 도구 재호출" 루프를 그래프로 표현.

---

## 3. 데이터 기반 분석

### microsoft/JARVIS (HuggingGPT) — https://github.com/microsoft/JARVIS
- **4단계**: Task Planning → Model Selection → Task Execution → Response Generation.
- **DAVIS 차용**: 박대표 질문이 들어오면 ERP/AIHUB/Gmail/Calendar 중 어떤 데이터 소스를 호출할지 먼저 계획 단계에서 결정. 이미 `google_tools.py`/`self_tools.py`가 있으므로 라우터 레이어만 추가.

### AutoGPT — https://github.com/Significant-Gravitas/AutoGPT
- **자율 목표 분해 + self-evaluation**: 결과를 스스로 평가하고 재시도.
- **DAVIS 차용**: 장시간 태스크(예: ERP 정산 분석)는 백그라운드 plan/critique 루프로 위임.

### llama_index / langgraph 결합 — RAG + Agent
- **Agentic RAG (2026 트렌드)**: 검색 → 평가(critic) → 재검색 → 합성.
- **DAVIS 차용**: 데코페이브 사내 문서/ERP 스냅샷을 인덱싱하면 "사실 기반 창의성" 가능.

---

## 4. 음성 통합 / JARVIS 스타일 어시스턴트

| 프로젝트 | 음성 | 특징 |
|---|---|---|
| **isair/jarvis** | O | "3인칭처럼 자연 대화", 위치/시간 인식, MCP 무한 도구, context-rot 방지 |
| **leon-ai/leon** | O | TypeScript, 스킬 모듈화, 로컬 우선 |
| **gbaptista/ion** | O | Picovoice 웨이크워드 + Nano Bots(ChatGPT/Gemini), 해킹 가능 |
| **PromtEngineer/Verbi** | O | STT/LLM/TTS 모듈 교체 실험용 (Deepgram/Cartesia/ElevenLabs/Ollama) |
| **m0hamed-ux/ai-voice-agent-livekit** | O | LiveKit + Gemini 2.5 Flash, 약간 비꼬는 인격 |
| **sukeesh/Jarvis** | O | 3.1k stars, 명령형 스킬 컬렉션 (구식이지만 스킬 카탈로그 참고) |

**DAVIS 차용 포인트**:
- isair/jarvis의 "context-rot 방지" 메모리 압축 패턴 (letta와 결합)
- Verbi의 모듈 교체 추상화 → STT(RealtimeSTT)/LLM(Anthropic)/TTS(edge-tts) 인터페이스 재정리
- ion의 Nano App 플러그인 모델 → `self_tools.py` 확장 시 참고

---

## 5. DAVIS가 즉시 도입할 7가지 패턴

1. **인격 3-블록 구조** (letta + crewAI): `persona`(데비스) / `human`(박대표) / `backstory` 분리, 시스템 프롬프트에서 분리해 `memory.py`로 관리.
2. **World Info 트리거** (SillyTavern): 데코페이브·AIHUB·ERP 키워드 매칭 시 관련 컨텍스트만 주입 → 토큰 30~50% 절감.
3. **First-Principles 자기 비판 루프** (principles + FPF): 응답 전 가정/반박/데이터 검증 3단 내부 사고.
4. **Plan→Select→Execute→Respond** (HuggingGPT): `task_planner.py`에 도구 라우팅 단계 추가.
5. **Analyst↔Creative 듀얼 에이전트** (autogen): 중요 결정 시 2-shot 내부 토론 후 합성.
6. **Reflection 그래프** (langgraph): 응답 → critic → 부족 시 도구 재호출 루프.
7. **Agent File 직렬화** (.af): 데비스 인격을 단일 파일로 백업/이식 → Claude 모델 변경 시 인격 손실 방지.

---

## 6. 핵심 한 줄 결론

> **JARVIS의 정수는 "스택"이 아니라 "구조"**다 — 음성 IO는 이미 v5에 있다. 부족한 것은 (a) 분리된 인격 블록, (b) 자기 비판 추론 루프, (c) 도구 라우팅 계획 단계. 이 셋만 letta+langgraph+SillyTavern 패턴으로 채우면 DAVIS는 박대표 전용 JARVIS가 된다.

---

## Sources

- [microsoft/JARVIS](https://github.com/microsoft/JARVIS)
- [letta-ai/letta](https://github.com/letta-ai/letta)
- [letta-ai/agent-file](https://github.com/letta-ai/agent-file)
- [leon-ai/leon](https://github.com/leon-ai/leon)
- [SillyTavern/SillyTavern](https://github.com/SillyTavern/SillyTavern)
- [sukeesh/Jarvis](https://github.com/sukeesh/Jarvis)
- [microsoft/autogen](https://github.com/microsoft/autogen)
- [joaomdmoura/crewAI](https://github.com/joaomdmoura/crewAI)
- [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)
- [Significant-Gravitas/AutoGPT](https://github.com/Significant-Gravitas/AutoGPT)
- [miltonian/principles](https://github.com/miltonian/principles)
- [ailev/FPF](https://github.com/ailev/FPF)
- [isair/jarvis](https://github.com/isair/jarvis)
- [PromtEngineer/Verbi](https://github.com/PromtEngineer/Verbi)
- [gbaptista/ion](https://github.com/gbaptista/ion)
- [m0hamed-ux/ai-voice-agent-livekit](https://github.com/m0hamed-ux/ai-voice-agent-livekit)
