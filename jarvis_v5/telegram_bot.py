"""DAVIS 텔레그램 봇 — 외부에서 박대표와 소통.

- 박대표 UID만 허용 (다른 사용자 무시)
- 텍스트 메시지 → Claude 응답 → 텔레그램 회신
- 음성 메시지 수신 → STT → 처리 → 음성 응답
- 로컬 DAVIS와 같은 메모리/세션 공유
- 시작 시 자동 인사 메시지 전송
"""

import asyncio
import logging
import os
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("davis.telegram")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_UIDS = {
    int(uid.strip())
    for uid in os.environ.get("TELEGRAM_ALLOWED_UIDS", "").split(",")
    if uid.strip().isdigit()
}


class DavisTelegramBot:
    """DAVIS 텔레그램 양방향 봇.

    사용법:
        bot = DavisTelegramBot(on_message=handle_text)
        bot.start()  # 백그라운드 스레드
    """

    def __init__(
        self,
        on_message: Callable[[str], str],
        on_start_message: str = None,
    ):
        self.token = TELEGRAM_TOKEN
        self.allowed_uids = ALLOWED_UIDS
        self.on_message = on_message
        self.on_start_message = on_start_message or "데비스가 준비되었습니다. 명령을 말씀해주세요."
        self._app = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self) -> bool:
        """텔레그램 봇 시작 (백그라운드 스레드)."""
        if not self.token:
            logger.warning("TELEGRAM_BOT_TOKEN not set")
            return False
        if not self.allowed_uids:
            logger.warning("TELEGRAM_ALLOWED_UIDS not set")
            return False

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"Telegram bot started (allowed UIDs: {self.allowed_uids})")
        return True

    def _run(self):
        """별도 스레드에서 asyncio 루프 시작."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_run())
        except Exception as e:
            logger.error(f"Telegram run error: {e}")

    async def _async_run(self):
        """봇 메인 루프."""
        from telegram import Update
        from telegram.ext import Application, MessageHandler, CommandHandler, filters

        self._app = Application.builder().token(self.token).build()

        # 시작 알림
        try:
            for uid in self.allowed_uids:
                await self._app.bot.send_message(
                    chat_id=uid,
                    text=f"🤖 {self.on_start_message}"
                )
        except Exception as e:
            logger.error(f"Start notification error: {e}")

        # 핸들러 등록
        self._app.add_handler(CommandHandler("start", self._handle_start))
        self._app.add_handler(CommandHandler("status", self._handle_status))
        self._app.add_handler(MessageHandler(filters.VOICE, self._handle_voice))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))

        # Polling
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()

        # 무한 대기
        while True:
            await asyncio.sleep(3600)

    def _is_allowed(self, update) -> bool:
        """허용된 사용자 체크."""
        if not update.effective_user:
            return False
        return update.effective_user.id in self.allowed_uids

    async def _handle_start(self, update, context):
        if not self._is_allowed(update):
            return
        await update.message.reply_text(
            "🤖 DAVIS 준비 완료\n"
            "텍스트 메시지를 보내거나 음성으로 명령하세요.\n"
            "/status - 상태 확인"
        )

    async def _handle_status(self, update, context):
        if not self._is_allowed(update):
            return
        await update.message.reply_text(
            f"🤖 DAVIS 작동 중\n"
            f"허용 UID: {self.allowed_uids}\n"
            f"봇 작동 정상"
        )

    async def _handle_text(self, update, context):
        """텍스트 메시지 처리."""
        if not self._is_allowed(update):
            logger.warning(f"Unauthorized UID: {update.effective_user.id if update.effective_user else 'unknown'}")
            return

        user_text = update.message.text.strip()
        logger.info(f"Telegram IN: {user_text[:80]}")

        # "생각 중" 타이핑 표시
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        try:
            # on_message 콜백 (동기)
            response = await asyncio.to_thread(self.on_message, user_text)
            if response:
                # 텔레그램 메시지 길이 제한 (4096자)
                if len(response) > 4000:
                    response = response[:4000] + "..."
                await update.message.reply_text(response)
                logger.info(f"Telegram OUT: {response[:80]}")
            else:
                await update.message.reply_text("응답을 생성하지 못했습니다.")
        except Exception as e:
            logger.error(f"Handler error: {e}")
            await update.message.reply_text(f"오류: {e}")

    async def _handle_voice(self, update, context):
        """음성 메시지 처리 (STT 후 텍스트로)."""
        if not self._is_allowed(update):
            return

        await update.message.reply_text("🎙️ 음성 인식 중...")

        try:
            voice = update.message.voice
            file = await voice.get_file()

            # OGG 다운로드
            tmp_dir = Path.home() / ".jarvis-cc" / "tmp"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            ogg_path = tmp_dir / f"tg_{update.message.message_id}.ogg"
            await file.download_to_drive(str(ogg_path))

            # faster-whisper로 STT (글로벌 접근)
            from faster_whisper import WhisperModel
            if not hasattr(self, "_stt_model"):
                self._stt_model = WhisperModel("tiny", device="cpu", compute_type="int8")

            segments, _ = self._stt_model.transcribe(str(ogg_path), language="ko")
            text = " ".join(seg.text for seg in segments).strip()

            if not text:
                await update.message.reply_text("음성을 인식하지 못했습니다.")
                return

            await update.message.reply_text(f"📝 {text}")

            # 일반 텍스트 처리
            response = await asyncio.to_thread(self.on_message, text)
            if response:
                if len(response) > 4000:
                    response = response[:4000] + "..."
                await update.message.reply_text(response)

            # 임시 파일 삭제
            try:
                ogg_path.unlink()
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Voice handler error: {e}")
            await update.message.reply_text(f"음성 처리 오류: {e}")

    def send_notification(self, text: str):
        """외부에서 알림 전송 (예: 작업 완료 보고)."""
        if not self._app or not self._loop:
            return

        async def _send():
            for uid in self.allowed_uids:
                try:
                    await self._app.bot.send_message(chat_id=uid, text=text)
                except Exception as e:
                    logger.error(f"send_notification error: {e}")

        asyncio.run_coroutine_threadsafe(_send(), self._loop)


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s')

    # .env 로드
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ[k.strip()] = v.strip()

    # 모듈 재로드
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    ALLOWED_UIDS = {int(u) for u in os.environ.get("TELEGRAM_ALLOWED_UIDS", "").split(",") if u.strip().isdigit()}

    def echo(text: str) -> str:
        return f"Echo: {text}"

    # 테스트: 10초 실행
    bot = DavisTelegramBot(on_message=echo)
    bot.token = TELEGRAM_TOKEN
    bot.allowed_uids = ALLOWED_UIDS

    if bot.start():
        print("봇 테스트 중. 10초간 메시지 대기...")
        import time
        time.sleep(10)
