"""세션 관리 — JSONL 기반 대화 이력 저장/복원.

참조: duck_talk src/shared/models.ts (JSONL session format).
"""

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SESSION_DIR = Path.home() / ".jarvis-cc" / "sessions"


class SessionManager:
    """JSONL 기반 세션 관리."""

    def __init__(self, session_dir: Path | None = None):
        self._session_dir = session_dir or SESSION_DIR
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._current_session_id: str = ""
        self._current_file: Optional[Path] = None

    def new_session(self) -> str:
        """새 세션 시작."""
        self._current_session_id = str(uuid.uuid4())[:8]
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}_{self._current_session_id}.jsonl"
        self._current_file = self._session_dir / filename
        logger.info(f"New session: {self._current_session_id}")
        return self._current_session_id

    def save_entry(self, role: str, text: str, metadata: dict | None = None):
        """대화 엔트리 저장."""
        if not self._current_file:
            self.new_session()

        entry = {
            "id": str(uuid.uuid4())[:12],
            "timestamp": time.time(),
            "role": role,       # "user" | "jarvis" | "system"
            "text": text,
        }
        if metadata:
            entry["metadata"] = metadata

        with open(self._current_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def load_session(self, session_file: str | Path) -> list[dict]:
        """세션 파일에서 모든 엔트리 로드."""
        path = Path(session_file)
        if not path.exists():
            return []

        entries = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries

    def list_sessions(self, limit: int = 20) -> list[dict]:
        """최근 세션 목록."""
        files = sorted(self._session_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
        sessions = []

        for f in files[:limit]:
            # 마지막 줄에서 미리보기 (duck_talk: 32KB seek 패턴)
            preview = ""
            try:
                size = f.stat().st_size
                read_size = min(size, 32768)
                with open(f, "r", encoding="utf-8") as fp:
                    if size > read_size:
                        fp.seek(size - read_size)
                    lines = fp.readlines()
                    for line in reversed(lines):
                        line = line.strip()
                        if line:
                            try:
                                entry = json.loads(line)
                                preview = entry.get("text", "")[:100]
                                break
                            except json.JSONDecodeError:
                                continue
            except Exception:
                pass

            sessions.append({
                "file": f.name,
                "modified": f.stat().st_mtime,
                "size": f.stat().st_size,
                "preview": preview,
            })

        return sessions

    @property
    def current_session_id(self) -> str:
        return self._current_session_id


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    sm = SessionManager()
    sid = sm.new_session()
    print(f"[session] New session: {sid}")

    sm.save_entry("user", "파이썬 오류 찾아줘")
    sm.save_entry("jarvis", "박대표님, 14번 줄 들여쓰기 오류입니다.")
    sm.save_entry("user", "수정해줘")
    sm.save_entry("jarvis", "박대표님, 수정을 완료했습니다.")

    sessions = sm.list_sessions()
    print(f"[session] Sessions: {len(sessions)}")
    for s in sessions:
        print(f"  {s['file']} ({s['size']}B) - {s['preview']}")

    print("[session] OK")
