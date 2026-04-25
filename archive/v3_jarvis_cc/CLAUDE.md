# JARVIS-CC v3 — Claude Code 컨텍스트 (archived)

> ⚠️ **ARCHIVED — 활성 버전 아님.** 활성 트리는 `jarvis_v5/`이며, 이 문서는 v3(`archive/v3_jarvis_cc/`) 한정 컨텍스트입니다.
> 루트 [CLAUDE.md](../../CLAUDE.md)와 [docs/VERSIONING.md](../../docs/VERSIONING.md)가 우선합니다.
> 이 폴더의 코드는 빌드/테스트 대상이 아니며, 수정 금지입니다.
>
> **프로젝트**: JARVIS-CC (Just A Rather Very Intelligent System for Claude Code)
> **경로**: `archive/v3_jarvis_cc/` (이전: `jarvis_cc/`)
> **목적**: 완전 자율 음성 AI 어시스턴트 — 웨이크워드 → Claude Code → TTS 응답

## 아키텍처

```
[웨이크워드 "자비스!"] → [활성화 시퀀스] → [Claude Code /voice]
         ↓                                          ↓
  [HUD 오버레이]                             [JSONL 로그 감시]
                                                    ↓
                                          [텍스트 정제 + 퍼소나]
                                                    ↓
                                          [edge-tts Worker Pool]
                                                    ↓
                                            [음성 응답 출력]
```

## 모듈 구조

| 모듈 | 파일 | 역할 |
|------|------|------|
| 설정 | `config.py`, `config.toml` | TOML 기반 전체 설정 |
| 텍스트 정제 | `text_cleaner.py` | 마크다운/코드/ANSI 제거, 기술용어 한국어 변환 |
| TTS 엔진 | `tts_engine.py` | edge-tts Worker Pool + MCI 재생 + SAPI 폴백 |
| 사운드 FX | `sound_fx.py` | pygame WAV 비동기 재생 |
| 퍼소나 | `persona.py` | JARVIS 버틀러 포맷 + 4단계 모드 |
| JSONL 감시 | `monitor.py` | Claude Code 응답 실시간 감지 |
| 웨이크워드 | `wake_word.py` | Porcupine "jarvis" + Win+J 핫키 |
| HUD | `overlay.py` | tkinter 반투명 오버레이 |
| 자동시작 | `startup.py` | Windows Task Scheduler |
| 상태머신 | `state_machine.py` | IDLE→ACTIVATING→LISTENING→PROCESSING→SPEAKING |
| 웹 UI | `web_ui/server.py` | localhost:8910 설정 페이지 |
| 세션 | `session.py` | JSONL 대화 이력 저장 |
| 메인 | `main.py` | 전체 통합 진입점 |

## 핵심 규칙

1. **Windows 11 전용**: MCI 오디오, schtasks, pynput 등 Windows API 사용
2. **UTF-8 필수**: sys.stdout/stderr를 UTF-8로 래핑 (cp949 문제 방지)
3. **비동기**: TTS는 asyncio Queue, 모니터는 threading, HUD는 tkinter mainloop
4. **퍼소나**: 모든 응답에 "박대표님, ..." 접두어 (butler 스타일)
5. **중복 방지**: message.id LRU (2000개) + 2초 debounce

## 실행

```bash
python -m jarvis_cc.main           # 전체 실행
python -m jarvis_cc.config         # 설정 테스트
python -m jarvis_cc.text_cleaner   # 텍스트 정제 테스트
python -m jarvis_cc.state_machine  # 상태 머신 테스트
```

## 의존성

- pvporcupine, pvrecorder (웨이크워드)
- edge-tts, pyttsx3 (TTS)
- pygame (사운드)
- pynput (핫키)
- pystray, pillow (트레이)
