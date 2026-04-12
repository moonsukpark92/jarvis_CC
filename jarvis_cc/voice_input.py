"""음성 입력 모듈 — 독립 PyAudio 스트림으로 사용자 발화 캡처.

wake_word의 스트림과 공유하지 않고 독립 스트림을 열어서 레이스 컨디션 방지.
"""

import logging
import tempfile
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np

from jarvis_cc.korean_filter import filter_korean_stt

logger = logging.getLogger(__name__)


class VoiceInput:
    """사용자 음성 → 텍스트 변환 (독립 스트림).

    wake_word 감지기와 같은 VAD/Whisper 모델을 공유하되,
    PyAudio 스트림은 **독립적으로 생성**하여 레이스 컨디션을 방지합니다.
    """

    SAMPLE_RATE = 16000
    FRAME_SAMPLES = 512       # Silero VAD 호환
    SILENCE_LIMIT_MS = 1500   # 1.5초 무음이면 발화 끝
    MIN_SPEECH_MS = 500       # 최소 0.5초
    MAX_SPEECH_MS = 15000     # 최대 15초
    TIMEOUT_MS = 15000        # 15초 내 발화 시작 안하면 타임아웃

    def __init__(self, vad_model, whisper_model):
        """VAD/Whisper 모델만 받고, 스트림은 자체 생성."""
        self._vad = vad_model
        self._whisper = whisper_model

    def listen(self) -> Optional[str]:
        """독립 스트림으로 사용자 발화를 듣고 텍스트로 반환."""
        import pyaudio
        import torch

        logger.info("Opening independent mic stream for voice input...")

        # 독립 PyAudio 스트림 생성
        pa = pyaudio.PyAudio()
        stream = None
        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.SAMPLE_RATE,
                input=True,
                frames_per_buffer=self.FRAME_SAMPLES,
            )

            # 마이크 버퍼 비우기 (0.5초)
            logger.info("Flushing mic buffer...")
            for _ in range(int(0.5 * self.SAMPLE_RATE / self.FRAME_SAMPLES)):
                stream.read(self.FRAME_SAMPLES, exception_on_overflow=False)

            logger.info("Listening for user command... (speak now)")

            speech_frames: list[bytes] = []
            silence_count = 0
            is_speaking = False
            start_time = time.time()

            frame_ms = self.FRAME_SAMPLES / self.SAMPLE_RATE * 1000
            silence_limit = int(self.SILENCE_LIMIT_MS / frame_ms)
            min_frames = int(self.MIN_SPEECH_MS / frame_ms)
            max_frames = int(self.MAX_SPEECH_MS / frame_ms)
            timeout_s = self.TIMEOUT_MS / 1000

            while True:
                # 타임아웃 (발화 시작 전만)
                if time.time() - start_time > timeout_s and not is_speaking:
                    logger.info("Voice input timeout (no speech)")
                    return None

                audio_data = stream.read(self.FRAME_SAMPLES, exception_on_overflow=False)
                audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
                audio_float = audio_int16.astype(np.float32) / 32768.0
                audio_tensor = torch.from_numpy(audio_float)

                speech_prob = self._vad(audio_tensor, self.SAMPLE_RATE).item()

                if speech_prob > 0.5:
                    if not is_speaking:
                        is_speaking = True
                        speech_frames = []
                        logger.info("User speaking...")
                    speech_frames.append(audio_data)
                    silence_count = 0

                    if len(speech_frames) >= max_frames:
                        break

                elif is_speaking:
                    speech_frames.append(audio_data)
                    silence_count += 1
                    if silence_count >= silence_limit:
                        break

            if len(speech_frames) < min_frames:
                logger.info("Speech too short")
                return None

            return self._transcribe(speech_frames)

        except Exception as e:
            logger.error(f"Voice input error: {e}")
            return None
        finally:
            # 독립 스트림 정리
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            pa.terminate()
            logger.info("Independent mic stream closed")

    def _transcribe(self, frames: list[bytes]) -> Optional[str]:
        """음성 프레임 → 텍스트."""
        all_audio = b"".join(frames)
        duration_ms = len(frames) * self.FRAME_SAMPLES / self.SAMPLE_RATE * 1000
        logger.info(f"Transcribing ({duration_ms:.0f}ms, {len(all_audio)} bytes)")

        tmp_path = Path(tempfile.mktemp(suffix=".wav"))
        try:
            with wave.open(str(tmp_path), "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.SAMPLE_RATE)
                wf.writeframes(all_audio)

            # 한국어 STT (속도 우선)
            segments, _ = self._whisper.transcribe(
                str(tmp_path), language="ko", beam_size=1, best_of=1,
            )
            text = " ".join(seg.text for seg in segments).strip()
            logger.info(f"STT raw: '{text}'")

            # 한국어 필터 적용
            filtered = filter_korean_stt(text)
            if filtered:
                logger.info(f"User said: '{filtered}'")
            else:
                logger.info("Filtered as noise")
            return filtered

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None
        finally:
            tmp_path.unlink(missing_ok=True)
