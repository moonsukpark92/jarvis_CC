"""TTS Worker Pool 엔진 — edge-tts + Windows MCI 재생 + SAPI 폴백.

참조:
  - claude-speak cc-speak.py: edge-tts async, MCI playback (ctypes winmm)
  - claude-code-tts worker.go: Worker Pool queue (2 workers, 50 slots)
"""

import asyncio
import ctypes
import logging
import os
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from jarvis_cc.config import TTSConfig

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TTSJob:
    id: str
    text: str
    status: JobStatus = JobStatus.PENDING
    error: str = ""
    created_at: float = field(default_factory=time.time)
    audio_path: Optional[Path] = None


class AudioPlayer:
    """pygame.mixer 기반 오디오 플레이어.

    MCI는 MP3 타입 문제로 소리가 안 남 → pygame.mixer로 교체.
    스레드 안전, 볼륨 제어, 중단 기능.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._playing = False
        self._init_done = False

    def _ensure_init(self):
        if not self._init_done:
            try:
                import pygame
                if not pygame.mixer.get_init():
                    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
                self._init_done = True
            except Exception as e:
                logger.error(f"pygame.mixer init error: {e}")

    def play(self, audio_path: Path, volume: int = 70) -> bool:
        """MP3 파일 재생 (블로킹). volume: 0-100."""
        self._ensure_init()
        if not self._init_done:
            return False

        with self._lock:
            self._playing = True

        try:
            import pygame
            pygame.mixer.music.load(str(audio_path))
            pygame.mixer.music.set_volume(volume / 100.0)
            pygame.mixer.music.play()
            logger.info(f"Playing: {audio_path.name} (vol={volume}%)")

            # 재생 완료 대기
            while pygame.mixer.music.get_busy() and self._playing:
                time.sleep(0.05)

            return True
        except Exception as e:
            logger.error(f"Playback error: {e}")
            return False
        finally:
            with self._lock:
                self._playing = False

    def stop(self):
        """현재 재생 즉시 중단."""
        with self._lock:
            self._playing = False
        try:
            import pygame
            pygame.mixer.music.stop()
        except Exception:
            pass

    @property
    def is_playing(self) -> bool:
        return self._playing


class SAPIFallback:
    """Windows SAPI 폴백 TTS (pyttsx3)."""

    def __init__(self, rate: int = 180):
        self._rate = rate
        self._engine = None

    def speak(self, text: str) -> bool:
        try:
            if self._engine is None:
                import pyttsx3

                self._engine = pyttsx3.init()
                self._engine.setProperty("rate", self._rate)
                # 한국어 음성 찾기
                voices = self._engine.getProperty("voices")
                for v in voices:
                    if "korean" in v.name.lower() or "ko" in v.id.lower():
                        self._engine.setProperty("voice", v.id)
                        break

            self._engine.say(text)
            self._engine.runAndWait()
            return True
        except Exception as e:
            logger.error(f"SAPI fallback error: {e}")
            return False


class TTSWorkerPool:
    """asyncio Queue 기반 TTS Worker Pool.

    참조: claude-code-tts worker.go (2 workers, 50 slots, Mutex).
    """

    def __init__(self, config: TTSConfig):
        self.config = config
        self._queue: asyncio.Queue[TTSJob] = asyncio.Queue(maxsize=config.queue_size)
        self._player = AudioPlayer()
        self._sapi = SAPIFallback()
        self._workers: list[asyncio.Task] = []
        self._job_counter = 0
        self._recent_jobs: list[TTSJob] = []
        self._running = False
        self._paused = False
        self._total_processed = 0
        self._total_failed = 0
        self._temp_dir = Path(tempfile.mkdtemp(prefix="jarvis_tts_"))
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(self):
        """워커 풀 시작."""
        self._running = True
        self._loop = asyncio.get_event_loop()
        for i in range(self.config.num_workers):
            task = asyncio.create_task(self._worker(i))
            self._workers.append(task)
        logger.info(f"TTS Worker Pool started: {self.config.num_workers} workers, queue size {self.config.queue_size}")

    async def stop(self):
        """워커 풀 중단."""
        self._running = False
        self._player.stop()
        for task in self._workers:
            task.cancel()
        self._workers.clear()
        # 임시 파일 정리
        import shutil

        shutil.rmtree(self._temp_dir, ignore_errors=True)

    async def submit(self, text: str) -> Optional[TTSJob]:
        """TTS Job 제출."""
        if not text.strip():
            return None

        self._job_counter += 1
        job = TTSJob(id=f"tts_{self._job_counter}", text=text)

        try:
            self._queue.put_nowait(job)
        except asyncio.QueueFull:
            job.status = JobStatus.FAILED
            job.error = "Queue is full"
            logger.warning("TTS queue full, job rejected")
            return job

        self._recent_jobs.append(job)
        if len(self._recent_jobs) > 100:
            self._recent_jobs = self._recent_jobs[-50:]

        return job

    async def _worker(self, worker_id: int):
        """워커 루프: 큐에서 가져와 TTS 생성 + 재생."""
        logger.info(f"TTS Worker {worker_id} started")
        while self._running:
            try:
                # 일시정지 체크
                while self._paused and self._running:
                    await asyncio.sleep(0.1)

                job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            job.status = JobStatus.PROCESSING
            try:
                # edge-tts로 MP3 생성
                audio_path = await self._generate_tts(job.text)
                job.audio_path = audio_path

                if audio_path and audio_path.exists():
                    # 블로킹 재생을 스레드에서 실행
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._player.play, audio_path, 70
                    )

                    job.status = JobStatus.COMPLETED
                    self._total_processed += 1
                else:
                    # edge-tts 실패 → SAPI 폴백
                    logger.warning("edge-tts failed, falling back to SAPI")
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._sapi.speak, job.text
                    )
                    job.status = JobStatus.COMPLETED
                    self._total_processed += 1

            except Exception as e:
                job.status = JobStatus.FAILED
                job.error = str(e)
                self._total_failed += 1
                logger.error(f"TTS Worker {worker_id} error: {e}")

            finally:
                # 임시 오디오 파일 정리
                if job.audio_path and job.audio_path.exists():
                    try:
                        job.audio_path.unlink()
                    except OSError:
                        pass

    async def _generate_tts(self, text: str) -> Optional[Path]:
        """edge-tts로 MP3 생성.

        참조: claude-speak cc-speak.py tts_edge_async.
        """
        try:
            import edge_tts

            output_path = self._temp_dir / f"tts_{self._job_counter}_{int(time.time())}.mp3"

            communicate = edge_tts.Communicate(
                text,
                self.config.voice,
                rate=self.config.rate,
                volume=self.config.volume,
            )
            await communicate.save(str(output_path))

            if output_path.exists() and output_path.stat().st_size > 0:
                return output_path
            return None

        except Exception as e:
            logger.error(f"edge-tts generation error: {e}")
            return None

    def stop_current(self):
        """현재 재생 중인 TTS 중단 (F2 키)."""
        self._player.stop()

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def clear_queue(self):
        """큐 비우기."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Exception:
                break

    def get_status(self) -> dict:
        return {
            "workers": self.config.num_workers,
            "queue_pending": self._queue.qsize(),
            "queue_size": self.config.queue_size,
            "total_processed": self._total_processed,
            "total_failed": self._total_failed,
            "is_playing": self._player.is_playing,
            "is_paused": self._paused,
        }


# ─── 동기 래퍼 (단독 테스트용) ──────────────────────────────────────────────


async def _test():
    config = TTSConfig()
    pool = TTSWorkerPool(config)
    await pool.start()

    job = await pool.submit("안녕하세요, 박대표님. 자비스 TTS 엔진 테스트입니다.")
    if job:
        print(f"[tts] Job submitted: {job.id} ({job.status.value})")

    # 잠시 대기
    await asyncio.sleep(10)
    print(f"[tts] Status: {pool.get_status()}")

    await pool.stop()
    print("[tts] Pool stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_test())
