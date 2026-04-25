# DAVIS v5 → JARVIS-급 업그레이드 연구 노트 (2026-04-21)

목표: sub-1.5s 첫 응답, 자연스러운 턴테이킹, 인터럽션 처리, 한국어 정확도.

## 1. 핵심 레퍼런스: RealtimeVoiceChat (KoljaB) — 500ms 달성 레시피

창시자 레이턴시 분해:
- LLM 첫 문장 조각: ~220ms
- TTS 첫 오디오 청크: ~80ms
- STT (base.en): <5ms
- 턴 감지 모델: ~20ms
- VAD: 무시 가능

DEFAULT_RECORDER_CONFIG (DAVIS에 그대로 이식 가능):
```python
DEFAULT_RECORDER_CONFIG = {
    "model": "base",                     # tiny→base (한국어 정확도 크게 향상)
    "realtime_model_type": "base",
    "language": "ko",
    "silero_sensitivity": 0.05,          # 현재 0.6 → 훨씬 낮게 (오탐 감소)
    "webrtc_sensitivity": 3,             # 가장 aggressive
    "post_speech_silence_duration": 0.7, # 현재 0.5 → 0.7 (말 중간 끊김 방지)
    "min_length_of_recording": 0.5,
    "min_gap_between_recordings": 0,
    "enable_realtime_transcription": True,   # ★ 실시간 부분 전사 → LLM 일찍 시동
    "realtime_processing_pause": 0.03,
    "silero_use_onnx": True,             # ★ ONNX로 VAD 가속
    "silero_deactivity_detection": True,
    "beam_size": 3,                      # 5→3 (지연 ↓)
    "beam_size_realtime": 3,
    "allowed_latency_limit": 500,
    "initial_prompt_realtime": "하늘은 파랗습니다. 오늘 날씨가... 회의는 세 시에...",
    "faster_whisper_vad_filter": False,
}
```

## 2. 한국어 Whisper 정확도 — initial_prompt 전략

- `initial_prompt`는 처음 30초에만 적용 (그 후 자기 출력으로 덮임)
- 고유명사/전문용어 주입 전용:
```python
initial_prompt="박문석, 박대표, 데비스, DAVIS, 데코페이브, 문실장, AIHUB, ERP, Decohub, 2026년, 회의, 스케줄."
```
- 문장 스타일 힌트(구두점/존댓말) 주입으로 포맷 개선:
```python
initial_prompt="안녕하세요. 네, 알겠습니다. 박대표님, 오늘 일정은 어떻게 되나요?"
```
- 장기적으로는 `o0dimplz0o/Whisper-Large-v3-turbo-STT-Zeroth-KO-v2` 같은 한국어 파인튜닝 모델 고려 (CTranslate2 변환 필요)
- ENERZAi: 13MB 한국어 특화 모델이 whisper-large-v3보다 한국어에서 앞섬 → tiny 대신 small/base 한국어 FT가 최적

## 3. VAD 파라미터 — 자연스러운 턴테이킹

LiveKit/Silero 권장 (`min_silence_duration` 개념):
- `activation_threshold`: 0.5 (0.5-0.75 범위 실사용, 조용한 사무실은 0.5)
- `min_speech_duration`: 0.05s
- `min_silence_duration`: 0.55s (턴 종료 판정)
- `prefix_padding_duration`: 0.5s

DAVIS 현재 `post_speech_silence_duration=0.5` → **0.7로 상향** 권장 (한국어는 조사에서 짧은 pause가 잦음).

## 4. 인터럽션 / Barge-in (Iron Man급 핵심)

### LiveKit Adaptive Interruption Handling 알고리즘
- CNN이 파형/prosody 200-500ms 분석 → "진짜 끼어들기" vs "mm-hmm/기침" 구분
- 성능: 86% precision / 100% recall @ 500ms overlap
- VAD 단순 barge-in의 51% 오탐 제거, 중앙값 216ms에 트리거
- 30ms 이내 추론 완료

### DAVIS에 당장 적용 가능한 간단 버전
TTS 재생 중에도 VAD를 계속 돌리고, 음성 감지 시 즉시 `pygame.mixer.music.stop()`:
```python
# 별도 thread에서 재생 중 마이크 감시
def watchdog_barge_in(recorder):
    while pygame.mixer.music.get_busy():
        if recorder.is_recording:  # RealtimeSTT가 음성 감지 중
            pygame.mixer.music.stop()
            # LLM 스트리밍도 중단 (generator close)
            break
        time.sleep(0.05)
```
- 조건: `silero_sensitivity=0.05` (매우 낮게) + 최소 300ms 연속 음성일 때만 중단 (기침 방어)
- 에코 취소: 스피커→마이크 피드백 방지용 AEC 필요 (윈도우는 `speechrecognition` + WebRTC AEC 또는 헤드셋 사용)

## 5. sub-1.5s 첫 응답 전략

현재 DAVIS 병목: 도구 호출 허용 루프(8턴) + 논스트리밍 messages.create + edge-tts 전체 합성.

### 즉시 적용 (예상 ~800-1200ms)
1. **스트리밍 API 사용**: `client.messages.stream(...)` + tool call 감지 시에만 agentic loop로 폴백
2. **문장 경계 감지 조기화**: 현재 `[.!?。]\s|[.!?。]$` → 한국어는 `[.!?。]\s*|[다요죠까]\s+` 도 고려 (존댓말 종결어미로 조기 TTS 시작)
3. **병렬 TTS 프리페치**: 문장 n 재생 중 문장 n+1 edge-tts 합성을 별도 thread에서 (현재는 순차)
4. **Claude Haiku 프롬프트 캐싱** (81% TTFT 감소): system prompt + memory context를 `cache_control: {"type": "ephemeral"}`로 표시

### edge-tts 병렬 합성 패턴
```python
from concurrent.futures import ThreadPoolExecutor
tts_pool = ThreadPoolExecutor(max_workers=3)
futures = []
for sentence in sentences_generator:
    futures.append(tts_pool.submit(synth_to_mp3, sentence))
# 재생은 FIFO로
for f in futures:
    play(f.result())
```

## 6. 콜드 스타트 제거 — 워밍업

현재 DAVIS는 STT 첫 호출에서 모델 로드/CUDA 컴파일로 2-5s 추가 지연. 해결:

```python
def warmup():
    # 1. STT 워밍: 무음 0.5s 더미 인퍼런스
    import numpy as np
    dummy = np.zeros(16000, dtype=np.float32)
    recorder.transcribe_audio(dummy)  # 또는 짧은 .wav 파일

    # 2. TTS 워밍: 짧은 음절을 조용히 합성 (재생 X)
    asyncio.run(edge_tts.Communicate("안", TTS_VOICE).save("/tmp/warmup.mp3"))

    # 3. Claude 워밍: 빈 호출로 TLS/커넥션/KV 캐시
    client.messages.create(model=CLAUDE_MODEL, max_tokens=1,
                           messages=[{"role":"user","content":"hi"}])

    # 4. pygame 믹서 사전 init (이미 있음 — 유지)
```
`main()` 초반 `speak("데비스 준비 중입니다.")` 직후 별도 daemon thread에서 실행.

## 7. JARVIS 페르소나 프롬프트 엔지니어링

현재 DAVIS 프롬프트는 "친한 친구" 톤. JARVIS는 "격식 있되 따뜻한 집사" — 수정 제안:

```
당신은 DAVIS(데비스)입니다. 박문석 대표님의 AI 집사입니다.

페르소나:
- 아이언맨의 JARVIS처럼 정중하되 무겁지 않음
- 차분하고 논리적, 필요할 때 은근한 재치
- 박대표님을 선제적으로 돕되 과시하지 않음

음성 대화 최적화:
- 한 번의 응답은 2문장 이내, 음성으로 들었을 때 명료하게
- 마크다운/이모지/코드블록 금지 (TTS가 읽을 수 없음)
- 숫자는 "세 시 반", "2026년 4월 21일" 형태로 풀어쓰기
- 문장은 "~입니다", "~하시겠습니까"로 끝내 TTS 경계 감지 용이

응답 지연 최소화:
- 복잡한 도구 결과는 먼저 한 문장 요약 후 세부 설명
- "잠시만요" 같은 휴지어는 절대 출력하지 않음 (지연 가중)
- 확신 없으면 "확인해드리겠습니다" 후 도구 호출
```

## 8. 즉시 적용 우선순위 체크리스트

1. [HIGH] `STT_MODEL = "tiny"` → `"base"` (한국어 정확도 대폭 향상, +200MB RAM)
2. [HIGH] `silero_sensitivity: 0.6` → `0.05`, `silero_use_onnx=True`
3. [HIGH] `initial_prompt` 추가 (고유명사 주입)
4. [HIGH] `post_speech_silence_duration: 0.5` → `0.7`
5. [HIGH] Claude API를 `messages.stream()`으로 전환 (도구 없을 때)
6. [HIGH] Prompt caching — system + memory context에 `cache_control` 추가
7. [MEDIUM] 워밍업 함수 추가 (main 시작 시 daemon thread)
8. [MEDIUM] edge-tts 병렬 프리페치 (ThreadPoolExecutor)
9. [MEDIUM] 한국어 문장 경계: `[다요죠까]\s` 추가
10. [LOW] Barge-in watchdog thread — pygame.mixer 재생 중 is_recording 감시
11. [LOW] LiveKit agents + Silero ONNX로 풀 마이그레이션 (큰 변경)
12. [LOW] Korean FT Whisper 모델로 교체 (`o0dimplz0o/Whisper-Large-v3-turbo-STT-Zeroth-KO-v2`)

## 9. 참고 소스
- [RealtimeVoiceChat](https://github.com/KoljaB/RealtimeVoiceChat) — 500ms 레퍼런스 구현
- [LiveKit Adaptive Interruption](https://livekit.com/blog/adaptive-interruption-handling)
- [ENERZAi Korean Whisper](https://enerzai.com/resources/blog/small-models-big-heat-conquering-korean-asr-with-low-bit-whisper)
- [stream2sentence](https://github.com/KoljaB/stream2sentence)
- [Whisper prompt engineering](https://medium.com/axinc-ai/prompt-engineering-in-whisper-6bb18003562d)
- [ruh.ai latency optimization](https://www.ruh.ai/blogs/voice-ai-latency-optimization)
