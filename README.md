# JARVIS-CC v5

> Just A Rather Very Intelligent System for Claude Code

실시간 음성 AI 어시스턴트. "자비스!"라고 부르면 Claude AI와 한국어 음성 대화가 가능합니다.

## 아키텍처

```
[마이크] → [Silero VAD] → [faster-whisper STT]
                                    ↓
                          [Anthropic Claude 스트리밍]
                                    ↓
                          [edge-tts → 스피커]
```

**핵심**: Claude가 토큰을 스트리밍하면 문장 단위로 즉시 TTS 재생. 전체 응답을 기다리지 않음.

## 설치

```bash
pip install -r jarvis_v5/requirements.txt
```

## 설정

`.env` 파일 생성:
```
ANTHROPIC_API_KEY=sk-ant-...
```

## 실행

```bash
python jarvis_v5/jarvis.py
```

## 기능

- 웨이크워드 "자비스" 한국어 인식
- Claude Sonnet 실시간 스트리밍 응답
- edge-tts 무료 한국어 TTS
- HUD 오버레이 (대화 로그)
- 대화 히스토리 유지

## 기술 스택

| 구성요소 | 기술 |
|---------|------|
| STT | RealtimeSTT (Silero VAD + faster-whisper) |
| LLM | Anthropic Claude Sonnet (스트리밍) |
| TTS | RealtimeTTS (EdgeEngine / edge-tts) |
| 음성 감지 | Silero VAD + WebRTC VAD |

## 비용

- STT: 무료 (로컬)
- TTS: 무료 (edge-tts)
- LLM: ~$5-27/월 (Anthropic API)
