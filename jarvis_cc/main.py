"""JARVIS-CC v3 — 메인 진입점.

전체 모듈 통합: 웨이크워드 + JSONL 감시 + TTS + HUD + 트레이.
"""

import asyncio
import io
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

def _setup_utf8():
    """Windows UTF-8 출력 보장 — main() 진입 시 한 번만 호출."""
    if sys.platform == "win32":
        try:
            # stdout/stderr가 아직 래핑되지 않은 경우만
            if hasattr(sys.stdout, "buffer"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            if hasattr(sys.stderr, "buffer"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from jarvis_cc.config import JarvisConfig
from jarvis_cc.state_machine import JarvisStateMachine, State, Event
from jarvis_cc.text_cleaner import process_for_speech, extract_speakable_chunks
from jarvis_cc.persona import JarvisPersona
from jarvis_cc.tts_engine import TTSWorkerPool
from jarvis_cc.sound_fx import SoundFX, ensure_assets
from jarvis_cc.monitor import JSONLMonitor
from jarvis_cc.wake_word import WakeWordDetector, HotkeyListener
from jarvis_cc.overlay import HUDOverlay
from jarvis_cc.session import SessionManager
from jarvis_cc.web_ui.server import WebUIServer
from jarvis_cc.claude_bridge import ClaudeBridge
from jarvis_cc.voice_input import VoiceInput

logger = logging.getLogger("jarvis_cc")


class JarvisCC:
    """JARVIS-CC 메인 컨트롤러."""

    def __init__(self, config: JarvisConfig):
        self.config = config

        # 상태 머신
        self.state = JarvisStateMachine()

        # 모듈 초기화
        self.persona = JarvisPersona(config.persona)
        self.sfx = SoundFX(config.sound)
        self.session = SessionManager()
        self.overlay = HUDOverlay(config.hud)
        self.web_ui = WebUIServer(config)
        self.claude = ClaudeBridge(session_name="JARVIS-CC")  # 독립 세션
        self.tts: TTSWorkerPool | None = None
        self.monitor: JSONLMonitor | None = None
        self.wake_detector: WakeWordDetector | None = None
        self.hotkey_listener: HotkeyListener | None = None

        # 이벤트 루프
        self._loop: asyncio.AbstractEventLoop | None = None
        self._running = False

        # 상태 전이 콜백 등록
        self.state.on_transition(self._on_state_change)

    async def start(self):
        """JARVIS-CC 시작."""
        self._loop = asyncio.get_event_loop()
        self._running = True

        logger.info("=" * 50)
        logger.info("JARVIS-CC v3.0 Starting...")
        logger.info("=" * 50)

        # 사운드 에셋 확인
        ensure_assets()

        # 세션 시작
        self.session.new_session()

        # TTS Worker Pool 시작
        self.tts = TTSWorkerPool(self.config.tts)
        await self.tts.start()

        # JSONL 모니터 비활성화 — JARVIS 자체 Claude 세션 사용
        # (향후 다른 Claude Code 세션 감시용으로 남겨둠)
        # self.monitor = JSONLMonitor(...)
        logger.info(f"Claude Bridge session: {self.claude.get_status()}")

        # HUD 오버레이 시작
        self.overlay.start()
        self.overlay.update_state("idle")
        self.overlay.append_dialog("system", "JARVIS-CC v3.0 시작됨")

        # 웹 UI 시작
        self.web_ui.start()
        logger.info(f"Settings UI: http://localhost:{self.config.web_ui.port}")

        # 웨이크워드 감지 시작
        self.wake_detector = WakeWordDetector(self.config.porcupine, on_wake=self._on_wake)
        wake_ok = self.wake_detector.start()
        if wake_ok:
            engine = self.wake_detector.engine_name
            self.overlay.append_dialog("system", f"웨이크워드: {engine} 엔진 활성화")
        else:
            logger.warning("Wake word detector not started")
            self.overlay.append_dialog("system", "웨이크워드: Win+J 핫키만 사용")

        # 핫키 리스너 시작
        self.hotkey_listener = HotkeyListener(self.config.hotkey, on_wake=self._on_wake)
        self.hotkey_listener.start()

        # F2 TTS 중단 핫키
        self._setup_f2_stop()

        # ESC 전체 중단
        self._setup_esc_abort()

        logger.info("JARVIS-CC ready. Say 'Jarvis!' or press Win+J")
        self.overlay.append_dialog("system", f"준비 완료. '{self.config.porcupine.keyword}!' 또는 {self.config.hotkey.hotkey}")

        # 시스템 트레이 (메인 스레드 블로킹)
        await self._run_tray()

    async def stop(self):
        """JARVIS-CC 종료."""
        logger.info("JARVIS-CC shutting down...")
        self._running = False

        if self.wake_detector:
            self.wake_detector.stop()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        if self.monitor:
            self.monitor.stop()
        if self.tts:
            await self.tts.stop()
        self.overlay.stop()
        self.web_ui.stop()
        self.sfx.cleanup()

        logger.info("JARVIS-CC stopped")

    # ─── 이벤트 핸들러 ──────────────────────────────────────────────────────

    def _on_wake(self):
        """웨이크워드 / 핫키 감지."""
        if self.state.state != State.IDLE:
            return

        self.state.trigger(Event.WAKE)

    def _on_state_change(self, old: State, event: Event, new: State):
        """상태 전이 콜백."""
        self.overlay.update_state(new.value)

        if new == State.ACTIVATING:
            self._handle_activating()
        elif new == State.IDLE and old == State.SPEAKING:
            self.sfx.play("deactivate")

    def _handle_activating(self):
        """빠른 대화 루프: 띵(듣기) → 듣기 → 띵(처리) → 응답 TTS.

        인사말 TTS 제거. 비프음으로만 상태 전달. 최소 지연.
        """
        def _activate():
            try:
                # 1. 띵! (듣기 시작 신호)
                self.sfx.play("activate", blocking=True)
                self.overlay.append_dialog("system", "듣는 중...")
                logger.info("LISTEN: beep played, waiting for voice...")

                # 2. 즉시 음성 입력 받기
                self.state.trigger(Event.READY)  # → LISTENING
                self.overlay.update_state("listening")

                voice_input = self._get_voice_input()
                if not voice_input:
                    logger.info("No voice input")
                    self.sfx.play("deactivate")
                    self.state.reset()
                    return

                # 3. 띵! (처리 시작 신호)
                self.sfx.play("beep", blocking=True)
                self.overlay.append_dialog("user", voice_input)
                self.session.save_entry("user", voice_input)
                logger.info(f"PROCESS: '{voice_input}'")

                self.state.trigger(Event.COMMAND)  # → PROCESSING
                self.overlay.update_state("processing")

                # VAD 일시정지 (TTS 피드백 방지)
                if self.wake_detector:
                    self.wake_detector.pause()

                # 4. Claude에 질문 (짧은 답변 요청)
                response = self.claude.ask(voice_input, timeout=30)

                if not response:
                    self.sfx.play("error")
                    self.state.reset()
                    return

                # 5. 최소 가공 후 즉시 TTS
                cleaned = process_for_speech(response)
                # brief 모드: 핵심만 (긴 설명 제거)
                formatted = self.persona.format_response(cleaned, "brief")
                logger.info(f"SPEAK: '{formatted[:80]}...'")

                self.state.trigger(Event.RESPONSE)  # → SPEAKING
                self.overlay.update_state("speaking")
                self.overlay.append_dialog("jarvis", formatted[:200])
                self.session.save_entry("jarvis", formatted)

                # TTS 재생
                self._speak_sync(formatted)
                self.sfx.play("done")

            except Exception as e:
                logger.error(f"Conversation error: {e}")
            finally:
                if self.wake_detector:
                    self.wake_detector.resume()
                self.state.reset()

        threading.Thread(target=_activate, daemon=True).start()

    def _speak_sync(self, text: str):
        """TTS 동기 재생 — 완료까지 블로킹. 최소 지연."""
        if not self._loop or not self.tts:
            return
        logger.info(f"TTS: '{text[:50]}...'")
        asyncio.run_coroutine_threadsafe(
            self.tts.submit(text), self._loop
        )
        # 재생 시작 대기 (최대 5초)
        for _ in range(50):
            time.sleep(0.1)
            if self.tts._player.is_playing:
                break
        # 재생 완료 대기
        while self.tts._player.is_playing:
            time.sleep(0.1)

    def _get_voice_input(self) -> str | None:
        """독립 스트림으로 사용자 음성 입력 받기.

        wake_word의 VAD/Whisper 모델만 공유하고, PyAudio 스트림은 독립 생성.
        """
        det = self.wake_detector._detector if self.wake_detector else None
        if not det or not hasattr(det, '_vad_model') or not hasattr(det, '_whisper_model'):
            logger.warning("Voice input not available (no VAD/Whisper)")
            return None

        vi = VoiceInput(det._vad_model, det._whisper_model)
        return vi.listen()

    def _on_claude_response(self, msg_id: str, raw_text: str):
        """Claude Code 새 응답 감지 (monitor 콜백)."""
        preview = raw_text[:80].replace('\n', ' ')
        logger.info(f"Claude response [{msg_id[:12]}]: '{preview}...'")

        # 텍스트 정제
        cleaned = process_for_speech(raw_text)
        if not cleaned.strip():
            logger.info("Response empty after cleaning, skipping")
            return

        # 퍼소나 포맷
        formatted = self.persona.format_response(cleaned)
        if not formatted.strip():
            logger.info("Response empty after persona, skipping")
            return

        logger.info(f"Speaking: '{formatted[:100]}...'")

        # 상태 전이
        self.state.trigger(Event.RESPONSE)

        # HUD + 세션 기록
        self.overlay.append_dialog("jarvis", formatted[:200])
        self.session.save_entry("jarvis", formatted)

        # VAD 일시정지 (TTS 소리 피드백 방지)
        if self.wake_detector:
            self.wake_detector.pause()

        # TTS 큐에 청크 단위로 추가
        self.sfx.play("beep")
        chunks = extract_speakable_chunks(formatted)

        if self._loop and self.tts:
            for chunk in chunks:
                asyncio.run_coroutine_threadsafe(
                    self.tts.submit(chunk), self._loop
                )

            # 마지막 청크 후 완료 사운드 + IDLE 전이 예약
            async def _after_speak():
                # 큐가 빌 때까지 대기 (안전한 체크)
                await asyncio.sleep(1)  # 최소 1초 대기 (워커가 job을 가져갈 시간)
                for _ in range(120):    # 최대 60초 대기
                    if not self.tts or not self._running:
                        return
                    queue_empty = self.tts._queue.empty()
                    not_playing = not self.tts._player.is_playing
                    if queue_empty and not_playing:
                        break
                    await asyncio.sleep(0.5)
                if self._running:
                    self.sfx.play("done")
                    self.state.trigger(Event.DONE)
                # VAD 재개
                if self.wake_detector:
                    self.wake_detector.resume()

            asyncio.run_coroutine_threadsafe(_after_speak(), self._loop)

    # ─── 핫키 ────────────────────────────────────────────────────────────────

    def _setup_f2_stop(self):
        """F2 키: TTS 재생 중단."""
        try:
            from pynput.keyboard import Key, Listener

            def on_press(key):
                if key == Key.f2 and self.tts:
                    logger.info("F2 pressed: stopping TTS")
                    self.tts.stop_current()
                    self.tts.clear_queue()
                    self.state.trigger(Event.DONE)
                elif key == Key.esc:
                    logger.info("ESC pressed: aborting")
                    if self.tts:
                        self.tts.stop_current()
                        self.tts.clear_queue()
                    self.state.trigger(Event.ABORT)

            listener = Listener(on_press=on_press)
            listener.daemon = True
            listener.start()
        except ImportError:
            logger.warning("pynput not available for F2/ESC hotkeys")

    def _setup_esc_abort(self):
        pass  # ESC는 _setup_f2_stop에서 통합 처리

    # ─── 시스템 트레이 ───────────────────────────────────────────────────────

    async def _run_tray(self):
        """시스템 트레이 아이콘 (pystray)."""
        try:
            import pystray
            from PIL import Image, ImageDraw

            # 간단한 아이콘 생성
            img = Image.new("RGB", (64, 64), color="#0D1117")
            draw = ImageDraw.Draw(img)
            draw.ellipse([16, 16, 48, 48], fill="#00B4FF")
            draw.text((24, 22), "J", fill="#0D1117")

            def on_settings(icon, item):
                import webbrowser
                webbrowser.open(f"http://localhost:{self.config.web_ui.port}")

            def on_show_hud(icon, item):
                self.overlay.show()

            def on_quit(icon, item):
                icon.stop()
                self._running = False

            menu = pystray.Menu(
                pystray.MenuItem("JARVIS-CC v3.0", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("설정 (Web UI)", on_settings),
                pystray.MenuItem("HUD 표시", on_show_hud),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("종료", on_quit),
            )

            icon = pystray.Icon("JARVIS-CC", img, "JARVIS-CC", menu)

            # 트레이를 별도 스레드에서 실행
            tray_thread = threading.Thread(target=icon.run, daemon=True)
            tray_thread.start()

            # 메인 루프
            while self._running:
                await asyncio.sleep(1)

            icon.stop()

        except ImportError:
            logger.warning("pystray/pillow not installed, running without tray icon")
            # 트레이 없이 메인 루프
            while self._running:
                await asyncio.sleep(1)


def main():
    """CLI 진입점."""
    _setup_utf8()

    # 로깅 설정
    log_dir = Path.home() / ".jarvis-cc" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stderr),  # stderr로 로그 (stdout 충돌 방지)
            logging.FileHandler(
                log_dir / "jarvis_cc.log", encoding="utf-8", mode="a"
            ),
        ],
    )

    # 설정 로드
    config = JarvisConfig.load()

    # JARVIS-CC 인스턴스
    jarvis = JarvisCC(config)

    # 시그널 핸들러
    def signal_handler(sig, frame):
        logger.info("Signal received, shutting down...")
        jarvis._running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 실행 — start() 내에서 _running=False로 종료하면 stop()도 같은 루프에서 실행
    async def _run():
        try:
            await jarvis.start()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.error(f"JARVIS-CC error: {e}")
        finally:
            await jarvis.stop()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
