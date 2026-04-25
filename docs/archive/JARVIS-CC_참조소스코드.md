# JARVIS-CC 참조 소스코드 목록

> GitHub 분석 기반 JARVIS-CC 개발 참조 레포지토리 전체 정리  
> 수집 일자: 2026.04 | 용도: JARVIS-CC v3 개발 참고자료

---

## 📌 목차

1. [양방향 음성 인터페이스](#1-양방향-음성-인터페이스)
2. [TTS (텍스트→음성)](#2-tts-텍스트음성)
3. [STT (음성→텍스트)](#3-stt-음성텍스트)
4. [웨이크워드 감지](#4-웨이크워드-감지)
5. [Claude Code Hook 연동](#5-claude-code-hook-연동)
6. [다목적 참조 (복합 기능)](#6-다목적-참조-복합-기능)

---

## 1. 양방향 음성 인터페이스

### 🥇 VoiceMode — mbailey
- **GitHub**: https://github.com/mbailey/voicemode
- **별칭**: syntax-syndicate fork → https://github.com/syntax-syndicate/claude-code-voice-mode
- **공식 사이트**: https://getvoicemode.com
- **언어**: Python
- **특징**:
  - Claude Code 공식 지원 MCP 플러그인
  - 양방향 실시간 대화 (STT + TTS)
  - 오프라인 로컬 모드: Whisper.cpp (STT) + Kokoro (TTS)
  - 클라우드 모드: OpenAI STT/TTS API
  - 스마트 VAD(Voice Activity Detection) 무음 감지
  - Windows WSL 지원
- **설치**:
  ```bash
  claude mcp add --scope user voicemode -- uvx --refresh voice-mode
  ```
- **JARVIS-CC 적용**: VAD 무음감지 로직 참조

---

### 🥈 duck_talk — dhuynh95
- **GitHub**: https://github.com/dhuynh95/duck_talk
- **언어**: TypeScript / Node.js
- **특징**:
  - 리뷰 모드: 음성 인식 후 전송 전 텍스트 확인 → 수락/거부/수정
  - 오인식 교정 학습: diff 저장 → 다음번 자동 교정
  - 세션 관리: Claude Code JSONL 기반 대화 이력 저장/복원
  - 음성으로 인터럽트(중단) 가능
  - Gemini Live 2세션 구조 (STT용 + TTS용 분리)
- **설치**:
  ```bash
  git clone https://github.com/dhuynh95/duck_talk.git
  npm install && npm run dev
  ```
- **JARVIS-CC 적용**: 리뷰 모드, 오인식 교정 사전(corrections.json), 세션 관리 구조

---

### mcp-voice-hooks — johnmatthewtennant
- **GitHub**: https://github.com/johnmatthewtennant/mcp-voice-hooks
- **언어**: Node.js (MCP 서버)
- **특징**:
  - 브라우저 내장 STT/TTS 사용 (API 키 불필요)
  - 트리거 워드 모드: 특정 단어 말하면 자동 전송
  - 자동 일시정지 감지로 자동 전송
  - Chrome/Safari 지원
  - 브라우저 UI: http://localhost:5111
- **설치**:
  ```json
  // ~/.claude/settings.json
  {
    "extraKnownMarketplaces": {
      "mcp-voice-hooks-marketplace": {
        "source": { "source": "git", "url": "https://github.com/johnmatthewtennant/mcp-voice-hooks.git" }
      }
    }
  }
  ```
- **JARVIS-CC 적용**: 트리거워드 방식 참조

---

### claude-code-voice — mckaywrigley
- **GitHub**: https://github.com/mckaywrigley/claude-code-voice
- **언어**: Python / Shell
- **특징**:
  - 완전 핸즈프리 구조
  - Claude Code Hook (UserPromptSubmit + Stop) 연동
  - macOS 전용 (Windows 미지원)
- **JARVIS-CC 적용**: Hook 기반 완전 자동화 개념 참조

---

## 2. TTS (텍스트→음성)

### 🥇 claude-speak — silverdolphin863
- **GitHub**: https://github.com/silverdolphin863/claude-speak
- **언어**: Python
- **특징**:
  - **JSONL 로그 감시 방식** — subprocess 없이 `~/.claude/projects/` 파일 감시
  - edge-tts 기반 (Microsoft Neural, 무료, 인터넷 필요)
  - 스마트 텍스트 정제: 코드블록/파일경로/ANSI/마크다운/스피너/box-drawing 전부 제거
  - Debounce: 빠른 출력 2초 배치처리 (버벅임 방지)
  - 중복 방지: message.id로 동일 메시지 재낭독 방지
  - 웹 설정 UI: http://localhost:8910 (목소리 미리듣기)
  - 400+ 목소리, 50+ 언어
  - Windows MCI 지원
  - 프로젝트별 목소리 설정 분리
- **설치**:
  ```bash
  git clone https://github.com/silverdolphin863/claude-speak.git
  # Windows PowerShell
  .\install.ps1
  ```
- **JARVIS-CC 적용**: ★ 아키텍처 핵심 참조 (JSONL 감시, Debounce, 중복방지, 웹UI)

---

### clarvis — nickpending  
- **GitHub**: https://github.com/nickpending/clarvis
- **언어**: TypeScript / Bun
- **특징**:
  - JARVIS 스타일 음성 알림 (버틀러 퍼소나)
  - LLM 요약: Claude 응답을 2-3문장으로 요약 후 낭독
  - 4단계 말하기 모드: `brief` / `normal` / `full` / `bypass`
  - 기술 용어 TTS 포맷팅: API→"A P I", JSON→"jason"
  - ElevenLabs 고품질 + 시스템TTS 폴백
  - TypeScript/Bun 사용 (20배 빠른 시작)
  - 오류는 항상 시스템TTS로 폴백 발화
- **JARVIS-CC 적용**: ★ JARVIS 퍼소나, 4단계 모드, 기술용어 변환 로직

---

### AgentVibes — paulpreibisch
- **GitHub**: https://github.com/paulpreibisch/AgentVibes
- **언어**: Node.js / npm
- **특징**:
  - 50+ 목소리, 30+ 언어
  - 성격 모드: 버틀러 / 캐주얼 / 친근한 전문가
  - Piper TTS (오프라인), ElevenLabs, Windows SAPI 지원
  - TUI (blessed.js) 관리 인터페이스
  - 원격 SSH 오디오 터널링 (PulseAudio)
  - Claude Code + Claude Desktop + OpenClaw 지원
- **설치**:
  ```bash
  npx agentvibes install
  ```
- **JARVIS-CC 적용**: 성격 모드, 다중 TTS 폴백 구조 참조

---

### claude-code-tts — ybouhjira
- **GitHub**: https://github.com/ybouhjira/claude-code-tts
- **언어**: Go
- **특징**:
  - Worker Pool 아키텍처 (비동기 큐 50슬롯, 워커 2개)
  - 6가지 고품질 음성: alloy, echo, fable, onyx, nova, shimmer
  - 모든 응답 자동 낭독 (Stop hook 연동)
  - 동시 재생 방지 (Mutex)
  - Windows PowerShell 지원
  - 독립 CLI 바이너리: `speak-text`
- **설치**:
  ```bash
  git clone https://github.com/ybouhjira/claude-code-tts.git
  make install
  ```
- **JARVIS-CC 적용**: Worker Pool TTS 큐 아키텍처 참조

---

### claude-code-voice-handler — markhilton
- **GitHub**: https://github.com/markhilton/claude-code-voice-handler
- **언어**: Python
- **특징**:
  - GPT-4o-mini로 긴 응답 자동 압축 (음성에 적합한 길이로)
  - 3가지 성격 모드: butler / casual / friendly professional
  - OpenAI TTS 불가 시 시스템TTS(macOS say / Linux espeak / Windows SAPI) 자동 폴백
  - Claude Code hooks 디렉토리 연동
- **설치**:
  ```bash
  git clone https://github.com/markhilton/claude-code-voice-handler ~/.claude/hooks/voice_notifications
  ```
- **JARVIS-CC 적용**: 다중 성격 모드, OpenAI→시스템 TTS 폴백 구조

---

### talkback-win (Medium 아티클 기반)
- **아티클**: https://blog.devgenius.io/building-a-voice-for-my-cli-code-agent-5f2d15b5b89e
- **언어**: Python
- **특징**:
  - Windows 11 전용 네이티브 Python TTS
  - edge-tts 기반, API 키 불필요
  - Windows 인코딩 버그 해결 방법 문서화
  - Claude Code / Codex CLI / Gemini CLI 모두 지원
  - `pip install talkback-win` 단일 설치
- **JARVIS-CC 적용**: Windows edge-tts 인코딩 처리 참조

---

## 3. STT (음성→텍스트)

### claude-stt — jarrodwatts
- **GitHub**: https://github.com/jarrodwatts/claude-stt
- **언어**: Python
- **특징**:
  - Claude Code 플러그인 방식
  - 실시간 스트리밍 STT (라이브 받아쓰기)
  - 말하는 동시에 텍스트가 화면에 표시
- **설치**:
  ```bash
  git clone https://github.com/jarrodwatts/claude-stt
  python scripts/setup.py --dev
  ```
- **JARVIS-CC 적용**: 스트리밍 STT 참조 (선택 기능)

---

### claudet — unclecode (Chrome 확장)
- **GitHub**: https://github.com/unclecode/claudet
- **언어**: JavaScript (Chrome Extension)
- **특징**:
  - Claude.ai 웹에 마이크 버튼 추가
  - Groq API / OpenAI Whisper STT 선택
  - 로컬 처리 (개인정보 보호)
  - Chrome Web Store 배포
- **JARVIS-CC 적용**: STT 프로바이더 전환 구조 참조

---

### claude-code-is-programmable — disler (voice_to_claude_code.py)
- **GitHub**: https://github.com/disler/claude-code-is-programmable
- **언어**: Python
- **특징**:
  - RealtimeSTT + OpenAI TTS 조합
  - 대화 ID로 세션 관리 (`--id`)
  - 초기 프롬프트 설정 (`--prompt`)
  - Claude Code SDK 직접 제어
- **실행**:
  ```bash
  uv run voice_to_claude_code.py
  uv run voice_to_claude_code.py --id "my-session" --prompt "hello world 만들어줘"
  ```
- **JARVIS-CC 적용**: 세션 ID 기반 대화 관리 참조

---

### claude-code-voice — phildougherty
- **GitHub**: https://github.com/phildougherty/claude_code_voice
- **언어**: Python
- **특징**:
  - Python 래퍼 방식
  - STT + TTS 통합 구현
- **JARVIS-CC 적용**: subprocess 래퍼 방식 참조

---

## 4. 웨이크워드 감지

### 🥇 Porcupine — Picovoice (권장)
- **GitHub**: https://github.com/Picovoice/porcupine
- **공식 사이트**: https://picovoice.ai/platform/porcupine/
- **문서**: https://picovoice.ai/docs/porcupine/
- **언어**: C (바인딩: Python, JS, Android, iOS 등)
- **특징**:
  - **"jarvis" 키워드 기본 내장** (별도 학습 불필요)
  - CPU 사용량 0.1% 미만 (항상 켜두어도 무방)
  - 딥러닝 기반, 소음/잔향 환경에서도 강인
  - Windows 네이티브 지원
  - 무료 AccessKey (1 디바이스)
  - 한국어 지원
  - 커스텀 웨이크워드: Picovoice Console에서 수초 내 학습
- **설치**:
  ```bash
  pip install pvporcupine pyaudio
  ```
- **기본 내장 키워드 목록**:
  - `jarvis`, `alexa`, `hey google`, `hey siri`, `computer`, `porcupine`, `bumblebee` 등
- **JARVIS-CC 적용**: ★ 웨이크워드 엔진 핵심 채택

---

### openWakeWord — dscripka (오픈소스 대안)
- **GitHub**: https://github.com/dscripka/openWakeWord
- **언어**: Python
- **특징**:
  - 완전 무료, 오픈소스 (Apache 2.0)
  - Raspberry Pi 3 단일 코어에서 15-20 모델 동시 실행 가능
  - 오탐율 < 0.5회/시간
  - 거짓 거부율 < 5%
  - 커스텀 모델 학습 가능
- **설치**:
  ```bash
  pip install openwakeword
  ```
- **주의**: Porcupine 대비 정확도 낮음 (68.6% vs 92.5%)
- **JARVIS-CC 적용**: Porcupine AccessKey 없을 때 폴백 대안

---

### Trigger-Talk — ManiAm
- **GitHub**: https://github.com/ManiAm/Trigger-Talk
- **언어**: Python
- **특징**:
  - Porcupine + Vosk 하이브리드 방식
  - WebSocket 인터페이스
  - 핫워드 감지 → 자동 STT 파이프라인 연결
- **JARVIS-CC 적용**: 웨이크워드→STT 파이프라인 연결 구조 참조

---

## 5. Claude Code Hook 연동

### claude-code-hooks — shanraisshan
- **GitHub**: https://github.com/shanraisshan/claude-code-hooks
- **언어**: Python / Shell
- **특징**:
  - Hook 종류별 전체 예제: PreToolUse, PostToolUse, Stop, SubagentStop, SessionStart, UserPromptSubmit, PermissionRequest, Notification
  - 버전별 변경 이력 정리
  - Best practice 가이드
- **JARVIS-CC 적용**: Hook 연동 구조 전체 참조

---

## 6. 다목적 참조 (복합 기능)

### Medium — Voice Control for Claude Code (Björn Büdenbender)
- **URL**: https://medium.com/@agentic.ai.forge/voice-control-for-claude-code-a-step-by-step-guide-to-local-speech-recognition-ffc4928a9aec
- **특징**:
  - VoiceMode + Whisper.cpp 로컬 설정 완전 가이드
  - GPU 가속 설정 (CUDA)
  - Fedora 42 최신 배포판 호환성 패치 방법
- **JARVIS-CC 적용**: 로컬 Whisper 서버 설정 참조

---

## 🛠 JARVIS-CC v3 채택 기술 매핑

| 기능 | 채택 방식 | 참조 프로젝트 |
|------|-----------|--------------|
| 부팅 자동 시작 | Task Scheduler (schtasks) | — (Windows 표준) |
| 웨이크워드 감지 | Porcupine ("jarvis" 내장) | Porcupine, Trigger-Talk |
| STT | Claude Code 내장 /voice | Anthropic 공식 |
| Claude Code 연동 | JSONL 로그 감시 (watchdog) | claude-speak |
| 텍스트 정제 | 마크다운+코드+ANSI+기술용어 | claude-speak, clarvis |
| TTS 엔진 | edge-tts + SAPI 폴백 | claude-speak, AgentVibes |
| TTS 큐 관리 | Worker Pool (asyncio Queue) | claude-code-tts |
| Debounce | 2초 배치처리 | claude-speak |
| 중복 방지 | message.id 체크 | claude-speak |
| JARVIS 퍼소나 | 버틀러 스타일 포맷 변환 | clarvis, markhilton |
| 4단계 모드 | brief/normal/full/bypass | clarvis |
| HUD 오버레이 | tkinter topmost 반투명 | — (자체 개발) |
| 사운드 이펙트 | pygame WAV 비동기 재생 | — (자체 개발) |
| 웹 설정 UI | Flask localhost:8910 | claude-speak |
| 세션 관리 | JSONL 저장/복원 | duck_talk |

---

*JARVIS-CC 개발 참조 문서 | DECOHUB 내부 자료 | 2026.04*
