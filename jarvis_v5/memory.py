"""DAVIS 메모리 시스템 — 단기 대화 버퍼 + 장기 사실 저장.

3층 구조:
  1. 세션 버퍼: 최근 10턴 (인메모리)
  2. 장기 사실: 사용자 선호/정보 (JSON + 임베딩)
  3. 시맨틱 검색: 질문 관련 사실 자동 호출

참조: Siri/Alexa 아키텍처, mem0 경량화 버전.
"""

import json
import logging
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("davis.memory")

MEMORY_DIR = Path.home() / ".jarvis-cc" / "memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
FACTS_PATH = MEMORY_DIR / "facts.json"
BUFFER_PATH = MEMORY_DIR / "buffer.json"


class DavisMemory:
    """DAVIS 메모리 관리자."""

    def __init__(self, anthropic_client=None):
        self.client = anthropic_client
        self._encoder = None  # 지연 로드
        self.facts: list[dict] = []
        self.buffer: list[dict] = []
        self._lock = threading.Lock()
        self._load()
        logger.info(f"Memory loaded: {len(self.facts)} facts, {len(self.buffer)} buffer turns")

    @property
    def encoder(self):
        """Sentence-Transformer 지연 로드."""
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading sentence-transformer (multilingual)...")
            self._encoder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        return self._encoder

    def _load(self):
        """디스크에서 로드."""
        try:
            if FACTS_PATH.exists():
                self.facts = json.loads(FACTS_PATH.read_text(encoding="utf-8"))
            if BUFFER_PATH.exists():
                data = json.loads(BUFFER_PATH.read_text(encoding="utf-8"))
                self.buffer = data[-10:]  # 최근 10턴만
        except Exception as e:
            logger.error(f"Load error: {e}")
            self.facts = []
            self.buffer = []

    def _save(self):
        """디스크에 저장."""
        try:
            FACTS_PATH.write_text(
                json.dumps(self.facts, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
            BUFFER_PATH.write_text(
                json.dumps(self.buffer[-20:], ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"Save error: {e}")

    def add_turn(self, user_msg: str, assistant_msg: str):
        """대화 턴 추가. 5턴마다 사실 추출."""
        with self._lock:
            self.buffer.append({
                "user": user_msg,
                "assistant": assistant_msg,
                "ts": time.time(),
            })
            # 버퍼 크기 제한
            self.buffer = self.buffer[-20:]
            self._save()

        # 5턴마다 백그라운드로 사실 추출
        if len(self.buffer) % 5 == 0:
            threading.Thread(target=self._extract_facts, daemon=True).start()

    def _extract_facts(self):
        """최근 5턴에서 사용자 사실 추출 (Haiku 사용)."""
        if not self.client:
            return
        try:
            recent = self.buffer[-5:]
            convo = "\n".join(
                f"사용자: {t['user']}\n어시스턴트: {t['assistant']}"
                for t in recent
            )

            prompt = f"""다음 대화에서 사용자(박대표님)에 대한 지속적인 사실만 추출하세요.
선호, 관심사, 반복되는 주제, 이름, 일정, 중요 정보 등.
한 줄에 하나씩, 간결하게. 일시적인 것은 제외.
추출할 게 없으면 'NONE' 출력.

대화:
{convo}

사실 (한국어):"""

            resp = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))

            new_facts = []
            for line in text.splitlines():
                line = line.strip("- *•").strip()
                if line and line.upper() != "NONE" and len(line) > 5:
                    # 중복 체크 (단순 문자열)
                    if not any(line == f["text"] for f in self.facts):
                        new_facts.append(line)

            if new_facts:
                # 임베딩 계산
                embeddings = self.encoder.encode(new_facts).tolist()
                with self._lock:
                    for text, emb in zip(new_facts, embeddings):
                        self.facts.append({
                            "text": text,
                            "embedding": emb,
                            "ts": time.time(),
                        })
                    # 최대 500개 유지
                    if len(self.facts) > 500:
                        self.facts = self.facts[-500:]
                    self._save()
                logger.info(f"Extracted {len(new_facts)} new facts")

        except Exception as e:
            logger.error(f"Fact extraction error: {e}")

    def retrieve(self, query: str, k: int = 3, threshold: float = 0.35) -> list[str]:
        """질문과 관련된 사실 검색."""
        if not self.facts:
            return []
        try:
            q_emb = self.encoder.encode(query)
            scores = []
            for f in self.facts:
                if "embedding" in f:
                    score = float(np.dot(q_emb, f["embedding"]) /
                                  (np.linalg.norm(q_emb) * np.linalg.norm(f["embedding"]) + 1e-8))
                    scores.append((score, f["text"]))
            scores.sort(reverse=True)
            return [text for score, text in scores[:k] if score > threshold]
        except Exception as e:
            logger.error(f"Retrieve error: {e}")
            return []

    def build_context(self, query: str) -> str:
        """현재 질문에 대한 메모리 컨텍스트 생성."""
        memories = self.retrieve(query, k=5)

        parts = []
        if memories:
            parts.append("### 사용자에 대해 알고 있는 사실:")
            for m in memories:
                parts.append(f"- {m}")

        if self.buffer:
            parts.append("\n### 최근 대화:")
            for t in self.buffer[-4:]:
                parts.append(f"사용자: {t['user'][:100]}")
                parts.append(f"나: {t['assistant'][:100]}")

        return "\n".join(parts) if parts else ""

    def get_status(self) -> dict:
        return {
            "facts_count": len(self.facts),
            "buffer_count": len(self.buffer),
        }

    def clear(self):
        """메모리 초기화 (주의)."""
        with self._lock:
            self.facts = []
            self.buffer = []
            self._save()


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    logging.basicConfig(level=logging.INFO)

    from anthropic import Anthropic
    import os
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    client = Anthropic()
    mem = DavisMemory(client)

    # 테스트
    mem.add_turn("안녕하세요", "네, 안녕하세요")
    mem.add_turn("내 이름은 박문석이야", "박문석님 반갑습니다")
    mem.add_turn("나는 서울에 살아", "서울 어디 계세요?")
    mem.add_turn("강남에 사는데 커피를 좋아해", "강남 좋은 카페 많죠")
    mem.add_turn("매일 아침 7시에 운동해", "꾸준하시네요")

    print("\n=== 사실 추출 대기 ===")
    time.sleep(15)

    print(f"\n상태: {mem.get_status()}")
    print("\n=== 컨텍스트 빌드 테스트 ===")
    print(mem.build_context("오늘 뭐 먹을까?"))
