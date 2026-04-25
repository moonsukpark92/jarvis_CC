"""DAVIS 작업 플래너 — 업무 지시를 단계로 분해하고 실행 추적.

패턴: AutoGPT/TaskWeaver의 경량 버전.
- 복잡한 요청을 단계(step)로 분해
- 각 단계 실행 결과 추적
- 완료 시 메모리에 저장하여 재활용
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("davis.planner")

TASKS_PATH = Path.home() / ".jarvis-cc" / "tasks.json"
TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)


class TaskPlanner:
    """간단한 작업 상태 추적."""

    def __init__(self, anthropic_client=None):
        self.client = anthropic_client
        self.tasks: list[dict] = []
        self._load()

    def _load(self):
        try:
            if TASKS_PATH.exists():
                self.tasks = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Load error: {e}")
            self.tasks = []

    def _save(self):
        try:
            TASKS_PATH.write_text(
                json.dumps(self.tasks[-100:], ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"Save error: {e}")

    def is_task_request(self, user_text: str) -> bool:
        """업무 지시인지 간단히 판별 (휴리스틱)."""
        task_keywords = [
            "해줘", "해주세요", "부탁", "정리", "확인해", "찾아", "검색",
            "이메일", "메일", "일정", "캘린더", "문서", "보고서",
            "실행", "설치", "생성", "만들어", "작성", "분석",
        ]
        return any(kw in user_text for kw in task_keywords)

    def plan(self, user_text: str) -> list[str]:
        """업무 지시 → 단계 리스트 생성."""
        if not self.client:
            return [user_text]

        try:
            prompt = f"""다음 사용자 지시를 실행 가능한 단계(step)로 분해하세요.
각 단계는 구체적이고 실행 가능해야 합니다. 단순한 대화는 NONE 출력.

지시: {user_text}

출력 형식 (한국어, 단계당 한 줄):
1. [단계 1]
2. [단계 2]
...
또는 'NONE' (단순 대화인 경우)"""

            resp = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in resp.content if hasattr(b, "text")).strip()

            if text.upper().startswith("NONE"):
                return []

            steps = []
            for line in text.splitlines():
                line = line.strip()
                # "1. [단계]" 또는 "1) 단계" 형식 파싱
                import re
                m = re.match(r"^\s*\d+[.)]\s*\[?([^\]]+)\]?", line)
                if m:
                    step = m.group(1).strip()
                    if step:
                        steps.append(step)

            return steps

        except Exception as e:
            logger.error(f"Plan error: {e}")
            return []

    def create_task(self, description: str, steps: list[str]) -> str:
        """새 작업 생성 → task_id 반환."""
        task_id = f"t_{int(time.time())}"
        self.tasks.append({
            "id": task_id,
            "description": description,
            "steps": steps,
            "completed_steps": [],
            "status": "in_progress",
            "created": time.time(),
            "results": [],
        })
        self._save()
        logger.info(f"Task created: {task_id} ({len(steps)} steps)")
        return task_id

    def complete_step(self, task_id: str, step_idx: int, result: str):
        """단계 완료 기록."""
        for task in self.tasks:
            if task["id"] == task_id:
                task["completed_steps"].append(step_idx)
                task["results"].append({"step": step_idx, "result": result})
                if len(task["completed_steps"]) == len(task["steps"]):
                    task["status"] = "completed"
                    task["completed"] = time.time()
                self._save()
                return

    def get_recent_tasks(self, limit: int = 5) -> list[dict]:
        return sorted(self.tasks, key=lambda t: t.get("created", 0), reverse=True)[:limit]

    def get_status(self) -> dict:
        in_progress = sum(1 for t in self.tasks if t.get("status") == "in_progress")
        completed = sum(1 for t in self.tasks if t.get("status") == "completed")
        return {
            "total": len(self.tasks),
            "in_progress": in_progress,
            "completed": completed,
        }


# ─── 주제 트래커 ──────────────────────────────────────────────────────

TOPICS = {
    "schedule": ["일정", "캘린더", "약속", "미팅", "회의", "스케줄"],
    "email": ["이메일", "메일", "편지", "메시지"],
    "search": ["검색", "찾아", "알려줘", "뭐야", "어때", "뭐지"],
    "code": ["코드", "프로그램", "개발", "함수", "버그"],
    "task": ["업무", "작업", "해줘", "정리", "보고서"],
    "personal": ["나", "내가", "박대표", "저"],
    "system": ["데비스", "davis", "너"],
}


class TopicTracker:
    """현재 대화 주제 추적."""

    def __init__(self):
        self.current_topic: Optional[str] = None
        self.history: list[tuple[str, float]] = []

    def detect_topic(self, text: str) -> Optional[str]:
        """텍스트에서 주제 감지."""
        if not text:
            return None
        text_lower = text.lower()
        scores = {}
        for topic, keywords in TOPICS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[topic] = score

        if not scores:
            return None
        return max(scores, key=scores.get)

    def update(self, text: str) -> Optional[str]:
        """주제 업데이트 + 전환 감지."""
        topic = self.detect_topic(text)
        if topic:
            self.history.append((topic, time.time()))
            self.history = self.history[-20:]

            if topic != self.current_topic:
                logger.info(f"Topic change: {self.current_topic} -> {topic}")
                self.current_topic = topic
                return topic

        return None


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    logging.basicConfig(level=logging.INFO)

    tracker = TopicTracker()
    texts = [
        "오늘 일정 확인해줘",
        "이메일 새로 온 거 있어?",
        "그거 말고 코드 버그 좀 봐줘",
        "내가 어제 뭐 했지?",
    ]
    for t in texts:
        topic = tracker.update(t)
        print(f"'{t}' -> topic={topic}")
