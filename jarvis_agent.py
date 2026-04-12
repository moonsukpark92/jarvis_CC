"""JARVIS-CC v4 — LiveKit Agents 기반 실시간 음성 AI 어시스턴트.

아키텍처:
  [브라우저 마이크/스피커] ↔ WebRTC ↔ [LiveKit Server] ↔ [이 Agent]
  Agent: Silero VAD → OpenAI Whisper STT → Claude Sonnet LLM → OpenAI TTS

실행:
  1. LiveKit Server: livekit-server/livekit-server.exe --dev
  2. Agent: python jarvis_agent.py dev
  3. 브라우저: https://agents-playground.livekit.io 접속
"""

import logging
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.agents.voice import AgentSession
from livekit.plugins import anthropic, openai, silero

logger = logging.getLogger("jarvis-agent")

# JARVIS 시스템 프롬프트
JARVIS_SYSTEM_PROMPT = """당신은 JARVIS(자비스)입니다. 박문석 대표님(박대표님)의 개인 AI 비서입니다.

규칙:
- 항상 한국어로 답하세요
- 2-3문장 이내로 짧고 핵심적으로 답하세요 (음성 대화용)
- 마크다운, 코드블록, 특수문자 사용 금지 (TTS가 읽어야 함)
- 박대표님에게 존댓말 사용
- 기술 용어는 쉽게 풀어서 설명
- 불확실한 정보는 "확인이 필요합니다"라고 솔직하게 답변

성격: 영화 아이언맨의 자비스처럼 정중하고 유능한 버틀러 스타일
"""


async def entrypoint(ctx: JobContext):
    """LiveKit Agent 진입점."""
    logger.info("JARVIS Agent starting...")

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    session = AgentSession(
        # VAD: Silero (로컬, 무료, <1ms)
        vad=silero.VAD.load(),

        # STT: OpenAI Whisper (한국어 지원, $0.006/분)
        stt=openai.STT(
            model="whisper-1",
            language="ko",
        ),

        # LLM: Anthropic Claude Sonnet (한국어 우수, ~$0.015/분)
        llm=anthropic.LLM(
            model="claude-sonnet-4-20250514",
            temperature=0.7,
        ),

        # TTS: OpenAI TTS (자연스러운 음성, $0.015/분)
        tts=openai.TTS(
            model="tts-1",
            voice="onyx",  # 낮은 남성 목소리 (JARVIS 스타일)
        ),
    )

    # 시스템 프롬프트 설정
    session.llm.system_prompt = JARVIS_SYSTEM_PROMPT

    logger.info("JARVIS Agent ready. Waiting for participant...")

    # 참가자가 연결되면 자동으로 대화 시작
    await session.start(
        ctx.room,
        agent_name="JARVIS",
    )

    logger.info("JARVIS Agent session started")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        ),
    )
