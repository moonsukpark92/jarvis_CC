# v3 — JARVIS-CC (archived)

- **마지막 활성 날짜**: 2026-04-13 (커밋 `f6fd379` 직전).
- **아카이빙 사유**: v5(DAVIS)로 아키텍처 전환. v3는 상태머신 + worker pool TTS 기반으로 안정적이지만, RealtimeSTT 스트리밍 + 문장 단위 TTS 프리페치가 첫 응답 지연을 더 줄여 활성 자리를 v5에 넘겼다.
- **외부 의존**: `openwakeword`, `faster-whisper`, `pvporcupine`(선택), `pyaudio`, `edge-tts`, `pygame`, `watchdog`, `pynput`, `pystray`, `pillow`, `pydantic`, `anthropic`. 활성 트리의 `requirements.txt`와 충돌하므로 **별도 가상환경 필수**.
- **롤백 절차**:
  ```bat
  python -m venv .venv-v3
  .venv-v3\Scripts\activate
  pip install -r archive\v3_jarvis_cc\..\..\<옛 requirements.txt>  :: 또는 위 의존성 수동 설치
  python archive\v3_jarvis_cc\main.py
  ```
- **수정 금지**. 버그 발견 시 활성 트리(`jarvis_v5/`)에 백포팅하거나, 진짜 v3로 돌아가야 한다면 `migrate/` 브랜치에서 활성 승격 절차를 다시 따른다.
