"""JSONL 로그 모니터 — Claude Code 응답 실시간 감시.

참조: claude-speak claude-speak.py SpeechMonitor (lines 276-568).
핵심 패턴: file_pos 추적, 0.5초 polling, message.id LRU 중복방지, 2초 debounce.
"""

import hashlib
import json
import logging
import os
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Callable, Optional

from jarvis_cc.config import MonitorConfig

logger = logging.getLogger(__name__)


class JSONLMonitor:
    """Claude Code JSONL 로그 실시간 감시.

    ~/.claude/projects/<encoded_cwd>/ 내의 JSONL 파일을 감시하여
    새 assistant 메시지를 감지하면 콜백을 호출한다.
    """

    def __init__(self, config: MonitorConfig, on_message: Callable[[str, str], None],
                 exclude_cwd: str | None = None):
        """
        Args:
            config: 모니터 설정
            on_message: 콜백 (message_id, text) — 새 응답 감지 시 호출
            exclude_cwd: 이 CWD의 프로젝트 JSONL은 무시 (자기 자신의 세션 제외)
        """
        self.config = config
        self.on_message = on_message
        self._exclude_cwd = exclude_cwd

        # 파일 추적
        self._current_file: Optional[Path] = None
        self._file_pos: int = 0
        self._file_mtime: float = 0.0

        # 중복 방지 (LRU OrderedDict, claude-speak 패턴)
        self._spoken_ids: OrderedDict[str, bool] = OrderedDict()

        # Debounce
        self._pending_text: str = ""
        self._pending_id: str = ""
        self._last_text_time: float = 0.0
        self._pending_lock = threading.Lock()

        # 제어
        self._running = False
        self._watch_thread: Optional[threading.Thread] = None
        self._debounce_thread: Optional[threading.Thread] = None
        self._start_time: float = 0.0  # 시작 후 무시 기간용

    def start(self):
        """감시 시작."""
        self._running = True
        self._start_time = time.time()  # 시작 후 5초간 무시
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._debounce_thread = threading.Thread(target=self._debounce_flusher, daemon=True)
        self._watch_thread.start()
        self._debounce_thread.start()
        logger.info("JSONL Monitor started")

    def stop(self):
        """감시 중단."""
        self._running = False
        if self._watch_thread:
            self._watch_thread.join(timeout=3)
        if self._debounce_thread:
            self._debounce_thread.join(timeout=3)
        logger.info("JSONL Monitor stopped")

    def find_active_jsonl(self) -> Optional[Path]:
        """가장 최근 수정된 Claude Code JSONL 파일 찾기.

        exclude_cwd가 설정된 경우, 해당 CWD의 프로젝트 폴더는 제외합니다.
        이것은 JARVIS-CC를 실행한 Claude Code 세션의 응답을 무시하기 위함.
        """
        projects_dir = Path(self.config.claude_projects_dir).expanduser()
        if not projects_dir.exists():
            return None

        # 제외할 프로젝트 디렉토리 이름 계산
        exclude_dir_name = None
        if self._exclude_cwd:
            # Claude Code는 CWD를 c--Users-infow-cowork-jarvis-project 형식으로 인코딩
            exclude_dir_name = self._exclude_cwd.replace("\\", "-").replace("/", "-").replace(":", "").strip("-")
            # Windows 경로 정규화
            exclude_dir_name_lower = exclude_dir_name.lower()

        # 모든 프로젝트 디렉토리에서 JSONL 찾기
        jsonl_files = []
        for project_dir in projects_dir.iterdir():
            if not project_dir.is_dir():
                continue

            # 자기 자신의 세션 제외
            if exclude_dir_name:
                dir_name_lower = project_dir.name.lower()
                if exclude_dir_name_lower in dir_name_lower or dir_name_lower in exclude_dir_name_lower:
                    continue

            for f in project_dir.glob("*.jsonl"):
                jsonl_files.append(f)

        if not jsonl_files:
            return None

        # 가장 최근 수정된 파일
        return max(jsonl_files, key=lambda f: f.stat().st_mtime)

    def _watch_loop(self):
        """메인 감시 루프 (0.5초 간격 polling).

        참조: claude-speak SpeechMonitor.watch() (lines 472-551).
        """
        while self._running:
            try:
                self._poll_once()
            except Exception as e:
                logger.error(f"Monitor poll error: {e}")
            time.sleep(self.config.poll_interval)

    def _poll_once(self):
        """한 번의 polling 사이클."""
        # 시작 후 5초간 무시 (자기 자신의 Claude Code 세션 메시지 방지)
        if time.time() - self._start_time < 5.0:
            return

        # 활성 JSONL 찾기
        active = self.find_active_jsonl()
        if active is None:
            return

        # 파일 교체 감지 (claude-speak: Windows는 mtime 비교)
        if self._current_file != active:
            logger.info(f"Watching new JSONL: {active.name}")
            self._current_file = active
            # 기존 내용은 건너뛰기 (파일 끝에서 시작)
            self._file_pos = active.stat().st_size
            self._file_mtime = active.stat().st_mtime
            return

        # 파일 크기 변화 감지
        try:
            stat = active.stat()
        except OSError:
            return

        current_size = stat.st_size
        current_mtime = stat.st_mtime

        # mtime으로 파일 교체 감지 (로그 rotation)
        if current_mtime < self._file_mtime:
            self._file_pos = 0
            self._file_mtime = current_mtime

        if current_size <= self._file_pos:
            return

        # 새 데이터 읽기
        try:
            with open(active, "r", encoding="utf-8") as f:
                f.seek(self._file_pos)
                new_data = f.read()
                self._file_pos = f.tell()
        except (OSError, UnicodeDecodeError) as e:
            logger.warning(f"Read error: {e}")
            return

        self._file_mtime = current_mtime

        # 라인별 처리
        for line in new_data.splitlines():
            line = line.strip()
            if not line:
                continue
            result = self._extract_assistant_message(line)
            if result:
                msg_id, text = result
                if not self._is_duplicate(msg_id):
                    self._record_spoken_id(msg_id)
                    self._add_to_debounce(msg_id, text)

    def _extract_assistant_message(self, line: str) -> Optional[tuple[str, str]]:
        """JSONL 라인에서 assistant 메시지 추출.

        참조: claude-speak extract_text_from_line (lines 152-188).
        """
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None

        # type == "assistant" 필터
        msg_type = data.get("type", "")
        if msg_type != "assistant":
            return None

        # 메시지 텍스트 추출
        message = data.get("message", {})
        content = message.get("content", "")

        # content가 list인 경우 (Claude API 형식)
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif isinstance(block, str):
                    texts.append(block)
            text = "\n".join(texts)
        elif isinstance(content, str):
            text = content
        else:
            return None

        if not text.strip():
            return None

        # message_id 추출 (claude-speak 패턴)
        msg_id = message.get("id", "")
        if not msg_id:
            msg_id = data.get("uuid", "")
        if not msg_id:
            # hash 폴백
            msg_id = "_hash_" + hashlib.sha256(text.encode()).hexdigest()[:16]

        return msg_id, text

    def _is_duplicate(self, message_id: str) -> bool:
        """중복 체크 (LRU OrderedDict)."""
        return message_id in self._spoken_ids

    def _record_spoken_id(self, message_id: str):
        """spoken ID 기록 + LRU 관리.

        참조: claude-speak _record_spoken_id (lines 419-429).
        """
        self._spoken_ids[message_id] = True
        # 최대 크기 초과 시 50% 제거
        if len(self._spoken_ids) > self.config.max_spoken_ids:
            to_remove = len(self._spoken_ids) // 2
            for _ in range(to_remove):
                self._spoken_ids.popitem(last=False)

    def _add_to_debounce(self, msg_id: str, text: str):
        """Debounce 버퍼에 추가."""
        with self._pending_lock:
            if self._pending_text:
                self._pending_text += "\n" + text
            else:
                self._pending_text = text
            self._pending_id = msg_id
            self._last_text_time = time.time()

    def _debounce_flusher(self):
        """Debounce: 2초간 새 텍스트 없으면 flush.

        참조: claude-speak _debounce_flusher() (lines 404-417).
        """
        while self._running:
            time.sleep(0.1)
            with self._pending_lock:
                if not self._pending_text:
                    continue
                elapsed_ms = (time.time() - self._last_text_time) * 1000
                if elapsed_ms < self.config.debounce_ms:
                    continue

                text = self._pending_text
                msg_id = self._pending_id
                self._pending_text = ""
                self._pending_id = ""

            # 콜백 호출
            try:
                self.on_message(msg_id, text)
            except Exception as e:
                logger.error(f"on_message callback error: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    def on_msg(msg_id: str, text: str):
        preview = text[:100].replace("\n", " ")
        print(f"[monitor] New message [{msg_id[:12]}...]: {preview}")

    config = MonitorConfig()
    monitor = JSONLMonitor(config, on_message=on_msg)

    jsonl = monitor.find_active_jsonl()
    if jsonl:
        print(f"[monitor] Found active JSONL: {jsonl}")
    else:
        print("[monitor] No active JSONL found")

    print("[monitor] Starting watch (Ctrl+C to stop)...")
    monitor.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
        print("[monitor] Stopped")
