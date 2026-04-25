"""Claude Code 브릿지 — claude-agent-sdk 스트리밍 + subprocess 폴백.

공식 Python SDK로 멀티턴 세션 유지 + 스트리밍 응답.
SDK 실패 시 subprocess 폴백.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)


def _find_claude_cli() -> str:
    found = shutil.which("claude") or shutil.which("claude.cmd")
    if found:
        return found
    npm_path = os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd")
    if os.path.exists(npm_path):
        return npm_path
    return "claude"


class ClaudeBridge:
    """JARVIS 전용 Claude Code 독립 세션.

    1순위: claude-agent-sdk (스트리밍, 빠름)
    2순위: subprocess claude -p (폴백)
    """

    def __init__(self, session_name: str = "JARVIS-CC"):
        self._session_name = session_name
        self._session_id: Optional[str] = None
        self._message_count = 0
        self._claude_cli = _find_claude_cli()
        self._use_sdk = False

        # SDK 사용 가능 여부 확인
        try:
            from claude_agent_sdk import query
            self._use_sdk = True
            logger.info("[Claude] Using claude-agent-sdk (streaming)")
        except ImportError:
            logger.info(f"[Claude] Using subprocess fallback ({self._claude_cli})")

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    @property
    def message_count(self) -> int:
        return self._message_count

    def ask(self, question: str, timeout: int = 60) -> Optional[str]:
        """Claude Code에 질문 (동기). 세션 유지."""
        if not question.strip():
            return None

        logger.info(f"[Claude] Q: '{question[:60]}...'")

        if self._use_sdk:
            try:
                result = asyncio.run(self._ask_sdk(question))
                if result:
                    self._message_count += 1
                    return result
            except Exception as e:
                logger.warning(f"[Claude] SDK error: {e}, falling back to subprocess")

        return self._ask_subprocess(question, timeout)

    async def _ask_sdk(self, question: str) -> Optional[str]:
        """claude-agent-sdk로 질문 (스트리밍)."""
        from claude_agent_sdk import query, AssistantMessage, TextBlock

        chunks = []
        options = {"maxTurns": 1}

        if self._session_id:
            options["resume"] = self._session_id

        async for message in query(
            prompt=question,
            options=options,
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        chunks.append(block.text)
            # 세션 ID 추출
            if hasattr(message, 'session_id') and message.session_id:
                self._session_id = message.session_id

        response = "\n".join(chunks).strip()
        if response:
            logger.info(f"[Claude] SDK A ({len(response)} chars)")
            return response
        return None

    def _ask_subprocess(self, question: str, timeout: int) -> Optional[str]:
        """subprocess 폴백."""
        # 짧은 답변 요청 (음성 대화용)
        voice_prompt = f"[음성 대화 모드] 2-3문장 이내로 짧고 핵심적으로 답해주세요. 마크다운 사용 금지. 질문: {question}"
        cmd = [self._claude_cli, "-p", voice_prompt, "--output-format", "json"]

        if self._session_id:
            cmd.extend(["--resume", self._session_id])
        else:
            cmd.extend(["--name", self._session_name])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                shell=(sys.platform == "win32"),
            )

            if result.returncode != 0:
                logger.error(f"[Claude] subprocess error: {result.stderr[:200]}")
                return None

            try:
                data = json.loads(result.stdout)
                if data.get("session_id"):
                    self._session_id = data["session_id"]
                response = data.get("result", "").strip()
            except json.JSONDecodeError:
                response = result.stdout.strip()

            if response:
                self._message_count += 1
                logger.info(f"[Claude] subprocess A ({len(response)} chars)")
                return response
            return None

        except subprocess.TimeoutExpired:
            logger.error(f"[Claude] timeout ({timeout}s)")
            return None
        except Exception as e:
            logger.error(f"[Claude] error: {e}")
            return None

    def new_session(self):
        self._session_id = None
        self._message_count = 0

    def get_status(self) -> dict:
        return {
            "session_id": self._session_id,
            "message_count": self._message_count,
            "use_sdk": self._use_sdk,
        }
