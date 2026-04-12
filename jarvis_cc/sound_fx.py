"""사운드 이펙트 — pygame.mixer 비동기 WAV 재생.

이벤트별 사운드 매핑, TTS와 별도 채널에서 재생.
"""

import logging
import os
import struct
import threading
import wave
from pathlib import Path
from typing import Optional

from jarvis_cc.config import SoundConfig

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).parent / "assets"

SOUND_EVENTS = {
    "activate": "activate.wav",
    "beep": "beep.wav",
    "done": "done.wav",
    "error": "error.wav",
    "deactivate": "deactivate.wav",
}


def _generate_sine_wav(path: Path, freq: float = 440.0, duration: float = 0.3,
                       volume: float = 0.5, sample_rate: int = 44100):
    """더미 WAV 파일 생성 (사인파)."""
    import math

    n_samples = int(sample_rate * duration)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_samples):
            t = i / sample_rate
            # 페이드 인/아웃
            envelope = 1.0
            fade = int(sample_rate * 0.02)
            if i < fade:
                envelope = i / fade
            elif i > n_samples - fade:
                envelope = (n_samples - i) / fade
            val = volume * envelope * math.sin(2 * math.pi * freq * t)
            wf.writeframes(struct.pack("<h", int(val * 32767)))


def ensure_assets():
    """assets/ 폴더에 더미 사운드 파일 생성 (없는 경우)."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    presets = {
        "activate.wav": [(880, 0.15, 0.4), (1320, 0.15, 0.5)],
        "beep.wav": [(1000, 0.08, 0.3)],
        "done.wav": [(660, 0.12, 0.3), (880, 0.12, 0.4)],
        "error.wav": [(220, 0.3, 0.5)],
        "deactivate.wav": [(880, 0.1, 0.3), (440, 0.2, 0.2)],
    }

    for filename, tones in presets.items():
        path = ASSETS_DIR / filename
        if not path.exists():
            logger.info(f"Generating placeholder sound: {filename}")
            # 가장 긴 톤으로 생성 (단순화)
            freq, dur, vol = tones[0]
            _generate_sine_wav(path, freq, dur, vol)


class SoundFX:
    """사운드 이펙트 재생기."""

    def __init__(self, config: SoundConfig):
        self.config = config
        self._mixer_ready = False
        self._lock = threading.Lock()
        self._init_mixer()

    def _init_mixer(self):
        """pygame.mixer 초기화."""
        if not self.config.enabled:
            return
        try:
            import pygame.mixer

            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            self._mixer_ready = True
            logger.info("pygame.mixer initialized")
        except Exception as e:
            logger.warning(f"pygame.mixer init failed: {e}, using winsound fallback")
            self._mixer_ready = False

    def play(self, event: str, blocking: bool = False):
        """이벤트 사운드 재생."""
        if not self.config.enabled:
            return

        filename = SOUND_EVENTS.get(event)
        if not filename:
            logger.warning(f"Unknown sound event: {event}")
            return

        path = ASSETS_DIR / filename
        if not path.exists():
            logger.warning(f"Sound file not found: {path}")
            return

        if blocking:
            self._play_sync(path)
        else:
            threading.Thread(target=self._play_sync, args=(path,), daemon=True).start()

    def _play_sync(self, path: Path):
        """동기 재생."""
        with self._lock:
            if self._mixer_ready:
                self._play_pygame(path)
            else:
                self._play_winsound(path)

    def _play_pygame(self, path: Path):
        try:
            import pygame.mixer

            sound = pygame.mixer.Sound(str(path))
            sound.set_volume(self.config.volume)
            sound.play()
            # 재생 완료 대기
            import time

            while pygame.mixer.get_busy():
                time.sleep(0.05)
        except Exception as e:
            logger.error(f"pygame play error: {e}")

    def _play_winsound(self, path: Path):
        """winsound 폴백 (Windows 전용)."""
        try:
            import winsound

            winsound.PlaySound(str(path), winsound.SND_FILENAME)
        except Exception as e:
            logger.error(f"winsound play error: {e}")

    def cleanup(self):
        if self._mixer_ready:
            try:
                import pygame.mixer

                pygame.mixer.quit()
            except Exception:
                pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ensure_assets()
    config = SoundConfig()
    sfx = SoundFX(config)
    print("[sound_fx] Playing activate sound...")
    sfx.play("activate", blocking=True)
    print("[sound_fx] Playing done sound...")
    sfx.play("done", blocking=True)
    print("[sound_fx] OK")
    sfx.cleanup()
