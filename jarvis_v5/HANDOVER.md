# DAVIS v5 → JARVIS급 업그레이드 핸드오버

> 작성일: 2026-04-26
> 목적: 다른 세션에서 이어서 진행할 수 있도록 현재 상태 + 다음 작업 정리

---

## 1. 현재 작동 상태 (v5)

### 정상 동작 확인됨
- ✅ 음성 인식 (RealtimeSTT + faster-whisper base, 한국어)
- ✅ 웨이크워드 "데비스" 엄격 매칭 (`wake_matcher.py`)
- ✅ Claude Haiku 4.5 스트리밍 + prompt caching (1h TTL)
- ✅ edge-tts + pygame 음성 출력 + 인터럽트 지원
- ✅ 한국어 문장 경계(다/요/까/죠/네) 즉시 TTS
- ✅ 메모리 (단기 버퍼 + 장기 사실, sentence-transformers 임베딩)
- ✅ 텔레그램 봇 `@decovis_bot` (UID 5440292004 박대표만 허용)
- ✅ Google API 14개 도구 (Gmail/Drive/Calendar)
- ✅ 자가 진화 (read/edit/restart_davis)
- ✅ 환경 정보 암호화 저장
- ✅ 워밍업 daemon (콜드스타트 제거)

### 실행
```
cd "C:\Users\infow\cowork\jarvis project"
python jarvis_v5/jarvis.py
```

---

## 2. 핵심 파일 매핑

```
jarvis_v5/
  jarvis.py              # 메인 진입점 (사용자 수정됨, anthropic_cache.system_with_caching 사용)
  memory.py              # 단기 버퍼 + 장기 사실 (임베딩)
  wake_matcher.py        # "데비스" 엄격 매칭 + 명령어 추출
  task_planner.py        # 작업 분해 + 주제 추적
  self_tools.py          # 자가 진화 도구 (TOOLS_SCHEMA 통합 빌더)
  google_tools.py        # Gmail/Drive/Calendar 5개 도구
  environment.py         # PC 환경 + 자격증명 암호화
  telegram_bot.py        # @decovis_bot 양방향
  anthropic_cache.py     # 사용자가 추가한 cache 헬퍼 (system_with_caching)
  korean_filter.py       # (구) 한국어 필터, wake_matcher가 대체
  jarvis_style_research.md  # 16개 GitHub 프로젝트 분석
  jarvis_upgrade_notes.md   # 성능 튜닝 연구
  HANDOVER.md            # 이 파일
~/.jarvis-cc/
  facts.json             # 장기 메모리
  buffer.json            # 단기 대화 버퍼
  google_credentials.json # OAuth 클라이언트
  google_token.json      # OAuth 토큰 (자동 갱신)
  environment.yaml.enc   # 암호화된 환경 정보
  environment.key        # Fernet 마스터 키 (600 권한)
  logs/jarvis_v5.log     # 실행 로그
.env                     # API 키 (.gitignore)
```

---

## 3. 다음 세션이 진행할 작업 (우선순위)

리서치 결과 (`jarvis_style_research.md`)에서 도출된 7가지 패턴 중 미적용 항목:

### Phase A: 인격 3-블록 분리 (30분, 효과 최대)
**참조**: letta-ai/letta + crewAI

**작업**: `memory.py`에 PersonaBlock 추가
```python
class PersonaBlock:
    persona: str    # "데비스는 박대표의 비서. 데이터 우선이지만 농담을 좋아함"
    human: str      # "박문석 대표. 데코페이브 CEO. 7년째 보좌"
    backstory: str  # "데코페이브 본사 IT실 출신..."
```

`jarvis.py`의 `SYSTEM_PROMPT`를 정적 페르소나만 남기고, 인격/사용자 정보는 PersonaBlock으로 이동. `system_with_caching`에 별도 캐시 블록으로 전달.

### Phase B: First-Principles 자기 비판 루프 (1시간)
**참조**: miltonian/principles + ailev/FPF

**작업**: `stream_claude` 직전에 내부 reasoning 단계 추가
```python
def first_principles_check(user_text, context) -> str:
    """1) 가정 추출 2) 가정 반박 3) 데이터 검증
    Haiku로 빠르게 실행, 결과를 system_blocks에 추가"""
```

복잡한 질문(왜?/어떻게?/추천)에만 적용. 단순 명령(일정 확인 등)은 스킵.

### Phase C: HuggingGPT 4단계 라우팅 (1시간)
**참조**: microsoft/JARVIS

**작업**: `task_planner.py`에 라우터 추가
```
사용자 입력 → [Plan] 도구 필요 여부 + 어떤 도구
            → [Select] 구체적 도구 선택 (Calendar? Gmail?)
            → [Execute] 도구 실행
            → [Respond] 결과 합성 → 음성 응답
```

현재는 Claude가 직접 도구 선택. 명시적 라우터 추가 시 토큰 절감 + 일관성.

### Phase D: World Info 트리거 (45분)
**참조**: SillyTavern

**작업**: 키워드 매칭 시 관련 컨텍스트 동적 주입
```python
WORLD_INFO = {
    "데코페이브": "본사 위치, 사업 분야...",
    "AIHUB": "박대표 다른 프로젝트, 박대표 BOT...",
    "ERP": "j3.jtranet.co.kr, 계정 MH1200...",
    "텔레그램": "decovis_bot, 박대표 UID 5440292004",
}
```
입력에 키워드 등장 시 해당 컨텍스트만 system_blocks에 추가.

### Phase E: Analyst↔Creative 듀얼 에이전트 (2시간)
**참조**: microsoft/autogen

**작업**: 중요 결정만 (긴 답변, 추천, 의사결정) 2-shot 내부 토론 → 합성

### Phase F: Reflection 그래프 (2시간)
**참조**: langchain-ai/langgraph

**작업**: 응답 → critic("출처 있나?", "데이터 일관성?") → 부족 시 도구 재호출

### Phase G: Agent File `.af` 직렬화 (30분)
**참조**: letta-ai/agent-file

**작업**: 인격 + 메모리 + 도구 정의를 단일 JSON으로 export/import. 모델 변경 시 인격 보존.

---

## 4. 알려진 이슈 / 개선 필요

| 이슈 | 우선순위 | 대응 |
|------|---------|------|
| 응답 속도 (현재 ~2초, 목표 ~1.2초) | High | Phase B/D로 토큰 절감 → TTFT ↓ |
| TV/배경 소음 오인식 | Medium | RealtimeVoiceChat 패턴 적용 (CNN barge-in) |
| 첫 응답 후 메모리 빈약 | High | Phase A 적용 시 해결 |
| Google OAuth 토큰 만료 시 자동 처리 | Low | 이미 refresh 구현됨 |
| 텔레그램 음성 메시지 → STT 첫 호출 시 모델 다운로드 | Low | 워밍업에 포함 권장 |

---

## 5. 박대표 환경 정보

- 사용자: 박문석 (devpark, 박대표)
- 텔레그램 UID: 5440292004
- 텔레그램 봇: `@decovis_bot` (토큰 .env)
- Google 계정: moonsukpark92@gmail.com
- 작업 디렉토리: `C:\Users\infow\cowork\jarvis project\`
- 관련 프로젝트: AIHUB (박대표 BOT, 별도), MOONSILJANG (아카이브)

---

## 6. 다음 세션 시작 명령 (복붙)

```
DAVIS v5 핸드오버 받았다. C:\Users\infow\cowork\jarvis project\jarvis_v5\HANDOVER.md를 먼저 읽고 현재 상태를 파악한 후, Phase A (인격 3-블록 분리)부터 진행한다. 자동 승인 모드, 박대표는 외부에 있어 텔레그램으로만 소통 가능. 막히면 stop하고 보고.
```

---

## 7. 백업/롤백

- Git: `https://github.com/moonsukpark92/jarvis_CC` (main 브랜치)
- 자가 진화 시 `~/.jarvis-cc/.backups/`에 자동 백업
- 메모리 백업: `~/.jarvis-cc/facts.json` 주기적으로 복사 권장
