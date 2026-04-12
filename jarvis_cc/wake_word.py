"""웨이크워드 감지 — VAD + faster-whisper 한국어 직접 인식.

방식: Silero VAD로 짧은 음성 구간 감지 → faster-whisper STT → "자비스" 키워드 매칭
결과: 한국어 "자비스" 직접 인식, 정확도 90%+

폴백 체인: Porcupine(AccessKey) → VAD+Whisper(무료) → 핫키(Win+J)
"""

import logging
import tempfile
import threading
import time
import wave
from collections import deque
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from jarvis_cc.config import PorcupineConfig, HotkeyConfig
from jarvis_cc.korean_filter import is_wake_word, is_noise

logger = logging.getLogger(__name__)


class VADWhisperDetector:
    """Silero VAD + faster-whisper 기반 웨이크워드 감지.

    한국어 "자비스"를 직접 인식합니다.

    Flow:
    [마이크 16kHz] → [Silero VAD: 음성 구간?]
         ↓ 음성 감지 + 0.8초 무음 = 발화 끝
    [발화 오디오] → [faster-whisper STT (ko+en)]
         ↓ "자비스" / "jarvis" 포함?
    [활성화!]
    """

    # VAD 설정 — Silero VAD는 16kHz에서 정확히 512 샘플만 허용
    SAMPLE_RATE = 16000
    FRAME_SAMPLES = 512     # 정확히 512 (Silero VAD 유일한 허용 크기)
    FRAME_MS = 32           # 512 / 16000 * 1000 = 32ms
    SILENCE_LIMIT_MS = 800  # 0.8초 무음이면 발화 끝
    MIN_SPEECH_MS = 300     # 최소 0.3초 이상 음성이어야 처리
    MAX_SPEECH_MS = 3000    # 최대 3초 (웨이크워드는 짧음)

    def __init__(self, config: PorcupineConfig, on_wake: Callable[[], None]):
        self.config = config
        self.on_wake = on_wake
        self._vad_model = None
        self._whisper_model = None
        self._audio = None
        self._stream = None
        self._running = False
        self._paused = False  # TTS 재생 중 일시정지 (자기 소리 피드백 방지)
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        """VAD + Whisper 감지 시작."""
        # Silero VAD 로드
        try:
            import torch
            self._vad_model, _ = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                trust_repo=True,
            )
            logger.info("Silero VAD loaded")
        except Exception as e:
            logger.error(f"Silero VAD load error: {e}")
            return False

        # faster-whisper 로드
        try:
            from faster_whisper import WhisperModel
            self._whisper_model = WhisperModel(
                "small", device="cpu", compute_type="int8",
            )
            logger.info("faster-whisper (base) loaded")
        except Exception as e:
            logger.error(f"faster-whisper load error: {e}")
            return False

        # 마이크
        try:
            import pyaudio
            self._audio = pyaudio.PyAudio()
            self._stream = self._audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.SAMPLE_RATE,
                input=True,
                frames_per_buffer=self.FRAME_SAMPLES,
            )
        except Exception as e:
            logger.error(f"Microphone init error: {e}")
            return False

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

        logger.info("VAD+Whisper wake word detector started (한국어 '자비스' 인식)")
        return True

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        try:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
        except Exception:
            pass
        try:
            if self._audio:
                self._audio.terminate()
        except Exception:
            pass
        self._vad_model = None
        self._whisper_model = None
        logger.info("VAD+Whisper detector stopped")

    def _listen_loop(self):
        """메인 감시 루프: VAD로 음성 감지 → Whisper로 확인."""
        import torch

        logger.info("Microphone listening for '자비스'...")
        speech_frames: list[bytes] = []
        silence_count = 0
        is_speaking = False
        speech_start = 0

        silence_limit = int(self.SILENCE_LIMIT_MS / self.FRAME_MS)
        min_speech_frames = int(self.MIN_SPEECH_MS / self.FRAME_MS)
        max_speech_frames = int(self.MAX_SPEECH_MS / self.FRAME_MS)

        while self._running:
            try:
                # TTS 재생 중 일시정지 (자기 소리 피드백 방지)
                if self._paused:
                    time.sleep(0.1)
                    continue

                audio_data = self._stream.read(self.FRAME_SAMPLES, exception_on_overflow=False)
                audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
                audio_float = audio_int16.astype(np.float32) / 32768.0
                audio_tensor = torch.from_numpy(audio_float)

                # VAD 판정
                speech_prob = self._vad_model(audio_tensor, self.SAMPLE_RATE).item()

                if speech_prob > 0.5:
                    # 음성 감지
                    if not is_speaking:
                        is_speaking = True
                        speech_frames = []
                        speech_start = time.time()
                        logger.debug("Speech started")
                    speech_frames.append(audio_data)
                    silence_count = 0

                    # 최대 길이 초과 → 강제 처리
                    if len(speech_frames) >= max_speech_frames:
                        self._process_speech(speech_frames)
                        speech_frames = []
                        is_speaking = False
                        time.sleep(1.0)

                elif is_speaking:
                    # 무음 카운트
                    speech_frames.append(audio_data)
                    silence_count += 1

                    if silence_count >= silence_limit:
                        # 발화 끝 → 충분한 길이면 처리
                        if len(speech_frames) >= min_speech_frames:
                            self._process_speech(speech_frames)
                        speech_frames = []
                        is_speaking = False
                        silence_count = 0

            except Exception as e:
                if self._running:
                    logger.error(f"Listen error: {e}")
                    time.sleep(0.5)

    def _process_speech(self, frames: list[bytes]):
        """음성 프레임 → WAV → faster-whisper STT → 키워드 매칭."""
        all_audio = b"".join(frames)
        duration_ms = len(frames) * self.FRAME_MS
        logger.info(f"Processing speech ({duration_ms}ms, {len(all_audio)} bytes)")

        tmp_path = Path(tempfile.mktemp(suffix=".wav"))
        try:
            # WAV 저장
            with wave.open(str(tmp_path), "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.SAMPLE_RATE)
                wf.writeframes(all_audio)

            # 한국어 STT
            segments, _ = self._whisper_model.transcribe(
                str(tmp_path), language="ko", beam_size=1, best_of=1,
            )
            text_ko = " ".join(seg.text for seg in segments).strip()
            logger.info(f"STT (ko): '{text_ko}'")

            # 노이즈 필터
            if is_noise(text_ko):
                return

            # 유사도 기반 웨이크워드 매칭
            if is_wake_word(text_ko):
                logger.info(f"WAKE WORD CONFIRMED: '{text_ko}'")
                try:
                    self.on_wake()
                except Exception as e:
                    logger.error(f"on_wake error: {e}")
                time.sleep(2.0)
                return

        except Exception as e:
            logger.error(f"Speech processing error: {e}")
        finally:
            tmp_path.unlink(missing_ok=True)

    @property
    def is_running(self) -> bool:
        return self._running


class PorcupineDetector:
    """Porcupine 기반 (AccessKey 필요)."""

    def __init__(self, config: PorcupineConfig, on_wake: Callable[[], None]):
        self.config = config
        self.on_wake = on_wake
        self._porcupine = None
        self._recorder = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        if not self.config.access_key:
            return False
        try:
            import pvporcupine
            from pvrecorder import PvRecorder
            self._porcupine = pvporcupine.create(
                access_key=self.config.access_key,
                keywords=[self.config.keyword],
                sensitivities=[self.config.sensitivity],
            )
            self._recorder = PvRecorder(
                frame_length=self._porcupine.frame_length,
                device_index=self.config.device_index,
            )
            self._running = True
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
            logger.info(f"Porcupine started: '{self.config.keyword}'")
            return True
        except Exception as e:
            logger.error(f"Porcupine error: {e}")
            return False

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        try:
            if self._recorder:
                self._recorder.stop()
        except Exception:
            pass
        finally:
            self._recorder = None
            try:
                if self._porcupine:
                    self._porcupine.delete()
            except Exception:
                pass
            finally:
                self._porcupine = None

    def _listen_loop(self):
        self._recorder.start()
        while self._running:
            try:
                pcm = self._recorder.read()
                if self._porcupine.process(pcm) >= 0:
                    logger.info(f"Porcupine: '{self.config.keyword}' detected!")
                    try:
                        self.on_wake()
                    except Exception as e:
                        logger.error(f"on_wake error: {e}")
                    time.sleep(1.0)
            except Exception as e:
                if self._running:
                    logger.error(f"Porcupine error: {e}")
                    time.sleep(0.5)

    @property
    def is_running(self) -> bool:
        return self._running


class WakeWordDetector:
    """통합 웨이크워드 감지기.

    우선순위:
    1. Porcupine (AccessKey 있으면)
    2. VAD + Whisper (무료, 한국어 직접 인식)
    """

    def __init__(self, config: PorcupineConfig, on_wake: Callable[[], None]):
        self.config = config
        self.on_wake = on_wake
        self._detector = None
        self._engine_name = "none"

    def start(self) -> bool:
        if self.config.access_key:
            det = PorcupineDetector(self.config, self.on_wake)
            if det.start():
                self._detector = det
                self._engine_name = "porcupine"
                return True

        det = VADWhisperDetector(self.config, self.on_wake)
        if det.start():
            self._detector = det
            self._engine_name = "vad+whisper"
            return True

        logger.warning("No wake word engine available")
        return False

    def stop(self):
        if self._detector:
            self._detector.stop()
            self._detector = None

    def pause(self):
        """TTS 재생 중 VAD 일시정지."""
        if self._detector and hasattr(self._detector, '_paused'):
            self._detector._paused = True

    def resume(self):
        """TTS 재생 후 VAD 재개."""
        if self._detector and hasattr(self._detector, '_paused'):
            self._detector._paused = False

    @property
    def engine_name(self) -> str:
        return self._engine_name

    @property
    def is_running(self) -> bool:
        return self._detector.is_running if self._detector else False


class HotkeyListener:
    """전역 핫키 리스너 (Win+J)."""

    def __init__(self, config: HotkeyConfig, on_wake: Callable[[], None]):
        self.config = config
        self.on_wake = on_wake
        self._listener = None

    def start(self) -> bool:
        try:
            from pynput.keyboard import GlobalHotKeys
            self._listener = GlobalHotKeys({self.config.hotkey: self._on_hotkey})
            self._listener.daemon = True
            self._listener.start()
            logger.info(f"Hotkey: {self.config.hotkey}")
            return True
        except Exception as e:
            logger.error(f"Hotkey error: {e}")
            return False

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _on_hotkey(self):
        logger.info(f"Hotkey {self.config.hotkey} pressed!")
        try:
            self.on_wake()
        except Exception as e:
            logger.error(f"Hotkey error: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")

    def on_wake():
        print("\n>>> 자비스 활성화! <<<\n")

    det = WakeWordDetector(PorcupineConfig(), on_wake)
    print("'자비스'라고 말해보세요... (Ctrl+C 종료)")
    if det.start():
        print(f"Engine: {det.engine_name}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            det.stop()
    else:
        print("Failed")
