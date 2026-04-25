"""웹 설정 UI — http.server 기반 localhost:8910.

참조: claude-speak configure.py ConfigHandler.
"""

import asyncio
import json
import logging
import os
import threading
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from jarvis_cc.config import JarvisConfig

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


class SettingsHandler(BaseHTTPRequestHandler):
    """설정 UI HTTP 핸들러."""

    config: JarvisConfig = None  # 클래스 변수로 주입

    def log_message(self, format, *args):
        logger.debug(format % args)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/settings":
            self._serve_file("settings.html", "text/html")
        elif path == "/api/voices":
            self._handle_voices()
        elif path == "/api/settings":
            self._handle_get_settings()
        elif path == "/api/status":
            self._handle_status()
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length else ""

        if path == "/api/settings":
            self._handle_save_settings(body)
        elif path == "/api/preview":
            self._handle_preview(body)
        else:
            self.send_error(404)

    def _serve_file(self, filename: str, content_type: str):
        filepath = STATIC_DIR / filename
        if not filepath.exists():
            self.send_error(404, f"File not found: {filename}")
            return

        content = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_voices(self):
        """edge-tts 음성 목록 반환."""
        try:
            import edge_tts

            voices = asyncio.run(edge_tts.list_voices())

            # 한국어 + 영어 필터
            result = []
            for v in voices:
                locale = v.get("Locale", "")
                if locale.startswith("ko") or locale.startswith("en"):
                    result.append({
                        "name": v.get("ShortName", ""),
                        "locale": locale,
                        "gender": v.get("Gender", ""),
                    })

            self._send_json({"voices": result})
        except Exception as e:
            self._send_json({"voices": [], "error": str(e)})

    def _handle_get_settings(self):
        """현재 설정 반환."""
        cfg = self.config
        self._send_json({
            "tts_voice": cfg.tts.voice,
            "tts_rate": cfg.tts.rate,
            "tts_volume": cfg.tts.volume,
            "persona_mode": cfg.persona.mode,
            "persona_style": cfg.persona.style,
            "owner_name": cfg.persona.owner_name,
            "hud_enabled": cfg.hud.enabled,
            "hud_opacity": cfg.hud.opacity,
            "sound_enabled": cfg.sound.enabled,
            "sound_volume": cfg.sound.volume,
            "hotkey": cfg.hotkey.hotkey,
            "wake_keyword": cfg.porcupine.keyword,
            "wake_sensitivity": cfg.porcupine.sensitivity,
        })

    def _handle_save_settings(self, body: str):
        """설정 저장."""
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        cfg = self.config

        # 업데이트
        if "tts_voice" in data:
            cfg.tts.voice = data["tts_voice"]
        if "tts_rate" in data:
            cfg.tts.rate = data["tts_rate"]
        if "persona_mode" in data:
            cfg.persona.mode = data["persona_mode"]
        if "persona_style" in data:
            cfg.persona.style = data["persona_style"]
        if "hud_enabled" in data:
            cfg.hud.enabled = bool(data["hud_enabled"])
        if "hud_opacity" in data:
            cfg.hud.opacity = float(data["hud_opacity"])
        if "sound_enabled" in data:
            cfg.sound.enabled = bool(data["sound_enabled"])
        if "sound_volume" in data:
            cfg.sound.volume = float(data["sound_volume"])

        # 파일 저장
        cfg.save()

        self._send_json({"status": "saved"})

    def _handle_preview(self, body: str):
        """TTS 미리듣기."""
        output = None
        try:
            data = json.loads(body)
            text = data.get("text", "안녕하세요, 자비스입니다.")
            voice = data.get("voice", self.config.tts.voice)

            import edge_tts
            import tempfile

            output = Path(tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name)
            comm = edge_tts.Communicate(text, voice)
            asyncio.run(comm.save(str(output)))
            if output.exists():
                audio_data = output.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(audio_data)))
                self.end_headers()
                self.wfile.write(audio_data)
            else:
                self._send_json({"error": "TTS generation failed"}, 500)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)
        finally:
            if output and output.exists():
                try:
                    output.unlink()
                except OSError:
                    pass

    def _handle_status(self):
        """시스템 상태 반환."""
        self._send_json({
            "status": "running",
            "version": "3.0.0",
        })


class WebUIServer:
    """웹 UI 서버 래퍼."""

    def __init__(self, config: JarvisConfig):
        self.config = config
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """웹 UI 서버 시작 (백그라운드)."""
        SettingsHandler.config = self.config

        self._server = HTTPServer(
            (self.config.web_ui.host, self.config.web_ui.port),
            SettingsHandler,
        )
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        logger.info(
            f"Web UI started: http://{self.config.web_ui.host}:{self.config.web_ui.port}"
        )

    def stop(self):
        if self._server:
            self._server.shutdown()
            logger.info("Web UI stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    config = JarvisConfig.load()
    server = WebUIServer(config)
    server.start()
    print(f"[web_ui] Settings UI: http://localhost:{config.web_ui.port}")
    print("[web_ui] Press Ctrl+C to stop")

    try:
        import time

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
