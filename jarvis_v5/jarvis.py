"""JARVIS-CC v5 — 실시간 음성 AI 어시스턴트 (완전 통합).

아키텍처: RealtimeSTT → Anthropic Streaming → RealtimeTTS
응답 지연: ~2초 (첫 음성 출력까지)

기능:
  - 웨이크워드 "자비스" (RealtimeSTT 내장 VAD + Whisper 키워드 감지)
  - Claude Sonnet 스트리밍 (문장 단위 즉시 TTS)
  - edge-tts 무료 한국어 음성
  - 대화 히스토리 유지 (세션)
  - HUD 오버레이 (tkinter)
  - 시스템 트레이 아이콘

실행:
  python jarvis_v5/jarvis.py
"""

import os
import sys
import re
import time
import queue
import threading
import logging
from pathlib import Path
from difflib import SequenceMatcher

# ─── UTF-8 + .env ────────────────────────────────────────────────────────

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# ─── 로깅 ────────────────────────────────────────────────────────────────

log_dir = Path.home() / ".jarvis-cc" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(log_dir / "jarvis_v5.log", encoding="utf-8", mode="a"),
    ],
)
logger = logging.getLogger("jarvis")

# ─── 설정 ────────────────────────────────────────────────────────────────

CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 300

SYSTEM_PROMPT = """당신은 JARVIS(자비스)입니다. 박문석 대표님의 개인 AI 비서입니다.

규칙:
- 한국어로 답하세요
- 2-3문장 이내로 짧고 핵심적으로 답하세요
- 마크다운, 코드블록, 특수문자, 이모지 사용 금지
- 존댓말 사용, 자연스러운 대화체
- 처음 인사할 때 "네, 박대표님" 으로 시작"""

TTS_VOICE = "ko-KR-InJoonNeural"
STT_MODEL = "small"
STT_LANGUAGE = "ko"

# 웨이크워드 변형 (Whisper 오인식 대응)
WAKE_VARIANTS = {
    "자비스", "자피스", "가비스", "자비", "아비스", "하비스",
    "져비스", "쟈비스", "자빗", "자빛", "자밑", "차비스",
    "자벼스", "자비수", "자비쓰", "자부스", "잡이스",
}


def is_wake_word(text: str) -> bool:
    """웨이크워드 유사도 매칭."""
    if not text or len(text.strip()) < 2:
        return False
    clean = re.sub(r"[,.\s!?~\-]", "", text.lower())
    for v in WAKE_VARIANTS:
        if v in clean or re.sub(r"\s", "", v) in clean:
            return True
    if "jarvis" in text.lower():
        return True
    # 유사도 매칭
    for i in range(len(clean) - 2):
        window = clean[i:i + 3]
        if SequenceMatcher(None, "자비스", window).ratio() >= 0.6:
            return True
    return False


def is_noise(text: str) -> bool:
    """Whisper 환각/노이즈 필터."""
    if not text or len(text.strip()) < 2:
        return True
    noise = [r"^네\.?$", r"^음+", r"MBC", r"자막", r"구독", r"시청해"]
    for p in noise:
        if re.match(p, text.strip()):
            return True
    return False


# ─── Claude 스트리밍 ─────────────────────────────────────────────────────

import anthropic

client = anthropic.Anthropic()
conversation_history: list[dict] = []


def stream_claude(user_text: str):
    """Claude 스트리밍 제너레이터 → RealtimeTTS.feed()에 연결."""
    conversation_history.append({"role": "user", "content": user_text})
    messages = conversation_history[-10:]
    full_response = ""

    try:
        with client.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                full_response += text
                yield text
    except Exception as e:
        logger.error(f"Claude error: {e}")
        yield "죄송합니다, 오류가 발생했습니다."
        full_response = "오류 발생"

    conversation_history.append({"role": "assistant", "content": full_response})


# ─── HUD 오버레이 ────────────────────────────────────────────────────────

class SimpleHUD:
    """간단한 tkinter HUD."""

    def __init__(self):
        self._queue = queue.Queue()
        self._thread = None
        self._root = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        import tkinter as tk
        self._root = tk.Tk()
        self._root.title("JARVIS-CC")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        try:
            self._root.attributes("-alpha", 0.9)
        except Exception:
            pass

        w, h = 350, 300
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        self._root.geometry(f"{w}x{h}+{sw - w - 20}+{sh - h - 60}")
        self._root.configure(bg="#0D1117")

        # 타이틀
        tf = tk.Frame(self._root, bg="#161B22", height=28)
        tf.pack(fill=tk.X)
        tf.pack_propagate(False)
        self._led = tk.Canvas(tf, width=10, height=10, bg="#161B22", highlightthickness=0)
        self._led.pack(side=tk.LEFT, padx=8, pady=9)
        self._led_item = self._led.create_oval(1, 1, 9, 9, fill="#3FB950")
        tk.Label(tf, text="JARVIS-CC v5", fg="#E6EDF3", bg="#161B22", font=("Consolas", 9, "bold")).pack(side=tk.LEFT)

        # 상태
        self._status = tk.Label(self._root, text="대기 중", fg="#8B949E", bg="#0D1117", font=("맑은 고딕", 9), anchor=tk.W)
        self._status.pack(fill=tk.X, padx=10, pady=4)

        # 대화 로그
        self._text = tk.Text(self._root, bg="#0D1117", fg="#E6EDF3", font=("맑은 고딕", 9),
                            wrap=tk.WORD, highlightthickness=0, borderwidth=0, state=tk.DISABLED)
        self._text.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        self._text.tag_configure("user", foreground="#58A6FF")
        self._text.tag_configure("jarvis", foreground="#3FB950")
        self._text.tag_configure("system", foreground="#8B949E")

        # 드래그
        self._dx = self._dy = 0
        tf.bind("<Button-1>", lambda e: setattr(self, '_dx', e.x) or setattr(self, '_dy', e.y))
        tf.bind("<B1-Motion>", lambda e: self._root.geometry(f"+{self._root.winfo_x()+e.x-self._dx}+{self._root.winfo_y()+e.y-self._dy}"))

        self._process_queue()
        self._root.mainloop()

    def _process_queue(self):
        try:
            while True:
                cmd, args = self._queue.get_nowait()
                if cmd == "status":
                    self._status.config(text=args[0])
                elif cmd == "dialog":
                    self._text.config(state=tk.NORMAL)
                    role, text = args
                    prefix = {"user": "나: ", "jarvis": "자비스: ", "system": ""}
                    self._text.insert(tk.END, f"{prefix.get(role, '')}{text}\n", role)
                    self._text.see(tk.END)
                    self._text.config(state=tk.DISABLED)
                elif cmd == "led":
                    colors = {"idle": "#3FB950", "listen": "#FFD700", "think": "#00B4FF", "speak": "#3FB950"}
                    self._led.itemconfig(self._led_item, fill=colors.get(args[0], "#6E7681"))
        except queue.Empty:
            pass
        if self._root:
            self._root.after(100, self._process_queue)

    def status(self, text: str):
        self._queue.put(("status", (text,)))

    def dialog(self, role: str, text: str):
        self._queue.put(("dialog", (role, text)))

    def led(self, state: str):
        self._queue.put(("led", (state,)))


# ─── 메인 ────────────────────────────────────────────────────────────────

def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set. Check .env file.")
        sys.exit(1)

    from RealtimeSTT import AudioToTextRecorder
    from RealtimeTTS import TextToAudioStream, EdgeEngine

    logger.info("=" * 50)
    logger.info("JARVIS-CC v5 Starting...")
    logger.info("=" * 50)

    # HUD
    hud = SimpleHUD()
    hud.start()
    hud.dialog("system", "JARVIS-CC v5 시작 중...")

    # TTS
    logger.info("Loading TTS...")
    hud.status("TTS 로딩 중...")
    engine = EdgeEngine(rate=10)
    engine.set_voice(TTS_VOICE)
    tts_stream = TextToAudioStream(engine)
    logger.info("TTS ready")

    # STT
    logger.info("Loading STT...")
    hud.status("STT 로딩 중...")
    recorder = AudioToTextRecorder(
        model=STT_MODEL,
        language=STT_LANGUAGE,
        post_speech_silence_duration=0.6,
        spinner=False,
        silero_sensitivity=0.4,
        webrtc_sensitivity=3,
        min_length_of_recording=0.3,
        min_gap_between_recordings=0.1,
        enable_realtime_transcription=False,
    )
    logger.info("STT ready")

    hud.status("준비 완료 — 말씀하세요")
    hud.dialog("system", "준비 완료. '자비스' 또는 아무 말이나 하세요.")
    hud.led("idle")

    print()
    print("=" * 50)
    print("  JARVIS-CC v5 — 실시간 음성 AI 어시스턴트")
    print("  말씀하세요. 자동으로 음성을 감지합니다.")
    print("  '자비스'로 호출하거나 바로 질문하세요.")
    print("  Ctrl+C로 종료")
    print("=" * 50)
    print()

    # 웨이크워드 모드 vs 자유 대화 모드
    wake_mode = True  # True: "자비스" 호출 후 대화, False: 항상 대화

    try:
        while True:
            # 1. 음성 감지
            hud.led("listen")
            hud.status("듣는 중..." if not wake_mode else "'자비스' 대기 중...")

            user_text = recorder.text()

            if not user_text or is_noise(user_text):
                continue

            logger.info(f"STT: '{user_text}'")

            # 웨이크워드 모드
            if wake_mode:
                if is_wake_word(user_text):
                    logger.info("Wake word detected!")
                    hud.dialog("system", "자비스 호출됨")
                    hud.status("말씀하세요...")
                    hud.led("listen")

                    # 인사 (짧은 TTS)
                    tts_stream.feed("네, 박대표님.")
                    tts_stream.play()

                    # 명령 대기
                    cmd_text = recorder.text()
                    if not cmd_text or is_noise(cmd_text):
                        hud.status("'자비스' 대기 중...")
                        hud.led("idle")
                        continue
                    user_text = cmd_text
                else:
                    continue  # 웨이크워드 아니면 무시

            # 2. 사용자 입력 표시
            hud.dialog("user", user_text)
            hud.led("think")
            hud.status("생각 중...")
            logger.info(f"User: {user_text}")
            print(f"\n>>> {user_text}")

            t0 = time.time()

            # 3. Claude 스트리밍 → TTS 즉시 재생
            token_gen = stream_claude(user_text)
            tts_stream.feed(token_gen)

            hud.led("speak")
            hud.status("응답 중...")
            tts_stream.play()

            elapsed = time.time() - t0

            # 4. 응답 표시
            if conversation_history:
                response = conversation_history[-1]["content"]
                hud.dialog("jarvis", response[:200])
                logger.info(f"JARVIS ({elapsed:.1f}s): {response[:100]}...")
                print(f"<<< {response}")

            hud.led("idle")
            hud.status("'자비스' 대기 중..." if wake_mode else "듣는 중...")

    except KeyboardInterrupt:
        print("\nJARVIS 종료...")
    finally:
        recorder.shutdown()
        engine.shutdown()
        logger.info("JARVIS stopped")


if __name__ == "__main__":
    main()
