# v4 — JARVIS Agent (LiveKit, archived)

- **마지막 활성 날짜**: 2026-04-13.
- **아카이빙 사유**: LiveKit Agents + WebRTC 브라우저 UI 실험. 로컬 마이크 직접 처리(v5)가 셋업이 단순하고 지연이 작아 활성 자리를 양보했다.
- **구성**:
  - `jarvis_agent.py` — LiveKit Agents 진입점 (Silero VAD → OpenAI Whisper STT → Claude → OpenAI TTS).
  - `start_jarvis_v4.bat` — 실행 스크립트.
  - `livekit-server/` — LiveKit 서버 바이너리 (gitignored, 로컬 디스크에만 존재).
- **외부 의존**: `livekit-agents`, `livekit-plugins-anthropic`, `livekit-plugins-openai`, `livekit-plugins-silero`. **별도 가상환경 필수**.
- **롤백 절차**:
  ```bat
  python -m venv .venv-v4
  .venv-v4\Scripts\activate
  pip install livekit-agents livekit-plugins-anthropic livekit-plugins-openai livekit-plugins-silero
  archive\v4_jarvis_agent\livekit-server\livekit-server.exe --dev &
  python archive\v4_jarvis_agent\jarvis_agent.py dev
  ```
- **수정 금지**.
