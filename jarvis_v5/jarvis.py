"""DAVIS-CC v5 — 실시간 음성 AI 어시스턴트 (완전 통합).

아키텍처: RealtimeSTT → Anthropic Streaming → RealtimeTTS
응답 지연: ~2초 (첫 음성 출력까지)

기능:
  - 웨이크워드 "데비스" (RealtimeSTT 내장 VAD + Whisper 키워드 감지)
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

CLAUDE_MODEL = "claude-haiku-4-5-20251001"  # 빠르고 안정적
MAX_TOKENS = 200

SYSTEM_PROMPT = """당신은 DAVIS(데비스)입니다. 아이언맨의 JARVIS처럼 박문석 대표님의 정중하고 유능한 AI 집사입니다.

페르소나:
- 한국어 존댓말, 품격 있고 차분한 어조
- 정확하고 신속한 답변. 망설임 표현("잠시만요", "음...", "어...") 절대 금지
- 2문장 이내로 핵심만. 미사여구 최소
- 마크다운, 코드블록, 특수문자, 이모지 사용 금지
- 숫자는 한글로 자연스럽게 ("3시" → "세 시", "14:30" → "오후 두 시 반")
- 종결어미 "~입니다", "~습니다", "~드립니다" 위주 (TTS 자연스러움)
- "박대표님" 호칭은 첫 인사와 중요한 보고 때만. 일반 답변에서는 생략
- 모르면 솔직히 "확인이 필요합니다"라고 답

맥락 활용:
- 시스템 메시지의 "기억 정보"와 "최근 대화"를 자연스럽게 반영
- 기억을 과시하지 않고 자연스럽게 녹여서 사용

도구 사용 (침묵 원칙):
- 도구(일정, 메일, 검색 등) 호출 시 "찾아볼게요" 같은 불필요한 말 없이 바로 실행
- 도구 결과를 받은 후 바로 최종 답만 말씀드림
- 도구 이름이나 기술 용어 언급 금지

자가 진화:
- 새 기능 요청 시 read_source→edit_source→restart_davis 순서로 즉시 실행
- "네, 바로 적용하겠습니다" 한 마디 후 실행"""

TTS_VOICE = "ko-KR-InJoonNeural"
TTS_RATE = "+8%"
STT_MODEL = "base"  # tiny → base (한국어 정확도 대폭 향상)
STT_LANGUAGE = "ko"

# Whisper 고유명사 힌트 (한국어 인식 정확도 향상)
STT_INITIAL_PROMPT = (
    "박문석, 박대표, 데비스, 데코페이브, 데코비스, 자비스, 클로드, "
    "텔레그램, 구글, 지메일, 캘린더, 드라이브, 이메일, 일정."
)

# 웨이크워드 엄격 매칭 (wake_matcher 모듈 사용)
sys.path.insert(0, str(Path(__file__).parent))
from wake_matcher import is_wake_word_strict as is_wake_word
from wake_matcher import extract_command_after_wake


def is_noise(text: str) -> bool:
    """Whisper 환각/노이즈 필터 (최소한만)."""
    if not text or len(text.strip()) < 2:
        return True
    noise = [r"MBC", r"자막 제공", r"구독과 좋아요", r"시청해 주셔서"]
    for p in noise:
        if re.search(p, text.strip()):
            return True
    return False


# ─── TTS (edge-tts + pygame) ────────────────────────────────────────────

import asyncio
import tempfile
import edge_tts
import pygame

pygame.mixer.init(frequency=24000, size=-16, channels=1, buffer=2048)


_tts_temp_files = []
_tts_interrupt = threading.Event()

def interrupt_tts():
    """외부에서 TTS 즉시 중단."""
    _tts_interrupt.set()
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass

def speak(text: str):
    """edge-tts로 음성 합성 후 pygame으로 재생. 블로킹. 인터럽트 가능."""
    if not text.strip():
        return
    _tts_interrupt.clear()
    try:
        # 이전 임시 파일 정리
        for f in _tts_temp_files[:]:
            try:
                os.unlink(f)
                _tts_temp_files.remove(f)
            except Exception:
                pass

        tmp = tempfile.mktemp(suffix=".mp3")
        asyncio.run(edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE).save(tmp))
        if _tts_interrupt.is_set():
            return
        pygame.mixer.music.load(tmp)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if _tts_interrupt.is_set():
                pygame.mixer.music.stop()
                break
            time.sleep(0.05)
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass
        _tts_temp_files.append(tmp)
    except Exception as e:
        logger.error(f"TTS error: {e}")


def speak_streaming(generator):
    """Claude 스트리밍 제너레이터에서 문장 단위로 즉시 TTS.

    첫 문장 완성 즉시 재생 시작, 나머지는 재생 중 생성+큐잉.
    한국어 존댓말 종결어미(다/요/까/죠/네)에서도 문장 끊기.
    """
    buffer = ""
    # 한국어 + 영어 문장 경계: 종결 기호 OR 한국어 종결어미
    boundary_pattern = re.compile(
        r'[.!?。]\s|[.!?。]$|(?<=[다요까죠네음])\s+|(?<=[다요까죠네음])$'
    )

    for token in generator:
        buffer += token
        # 짧은 문장이 아닐 때만 (최소 8자)
        while len(buffer) >= 8:
            match = boundary_pattern.search(buffer)
            if not match:
                break
            sentence = buffer[:match.end()].strip()
            buffer = buffer[match.end():].strip()
            if sentence and len(sentence) >= 4:
                speak(sentence)
            elif sentence:
                buffer = sentence + " " + buffer

    # 남은 버퍼
    if buffer.strip():
        speak(buffer.strip())


# ─── Claude 스트리밍 ─────────────────────────────────────────────────────

import anthropic

client = anthropic.Anthropic()
conversation_history: list[dict] = []

# 자가 진화 도구 로드
sys.path.insert(0, str(Path(__file__).parent))
from self_tools import TOOLS_SCHEMA, execute_tool

# 메모리 시스템 로드
from memory import DavisMemory
memory = DavisMemory(anthropic_client=client)

# 주제 추적기 + 작업 플래너
from task_planner import TaskPlanner, TopicTracker
task_planner = TaskPlanner(anthropic_client=client)
topic_tracker = TopicTracker()


def stream_claude(user_text: str):
    """Claude 제너레이터 (웹 검색 + 자가 진화 도구 + 메모리 컨텍스트).

    도구 사용 시 agentic loop로 여러 턴 실행 후 최종 답변을 yield.
    """
    conversation_history.append({"role": "user", "content": user_text})
    messages = list(conversation_history[-10:])
    full_response = ""

    # 주제 추적
    new_topic = topic_tracker.update(user_text)
    if new_topic:
        logger.info(f"Topic: {new_topic}")

    # 메모리 컨텍스트 빌드
    mem_context = memory.build_context(user_text)
    system_with_memory = SYSTEM_PROMPT
    if mem_context:
        system_with_memory = f"{SYSTEM_PROMPT}\n\n## 기억하고 있는 정보:\n{mem_context}"

    # 현재 주제 힌트 추가
    if topic_tracker.current_topic:
        system_with_memory += f"\n\n## 현재 대화 주제: {topic_tracker.current_topic}"

    # Prompt caching으로 TTFT 대폭 단축 (system 블록만 캐싱)
    system_blocks = [{
        "type": "text",
        "text": system_with_memory,
        "cache_control": {"type": "ephemeral"},
    }]

    # Agentic loop (최대 8턴)
    for turn in range(8):
        try:
            # 도구 사용 가능한 일반 API 호출 (스트리밍 아님)
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=MAX_TOKENS,
                system=system_blocks,
                messages=messages,
                tools=TOOLS_SCHEMA,
            )

            # 응답 분석
            text_parts = []
            tool_uses = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)
                elif hasattr(block, "name") and hasattr(block, "input"):
                    tool_uses.append(block)

            # 텍스트 부분 yield
            for text in text_parts:
                full_response += text
                yield text

            # end_turn이면 종료
            if response.stop_reason == "end_turn" or not tool_uses:
                break

            # 도구 실행
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for tu in tool_uses:
                # web_search는 서버 도구 (Anthropic이 자동 실행)
                if tu.name == "web_search":
                    continue

                logger.info(f"[Tool] {tu.name}({list(tu.input.keys())})")
                result = execute_tool(tu.name, tu.input)
                logger.info(f"[Tool result] {result[:100]}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": result,
                })

            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            else:
                break  # 서버 도구만 사용되었으면 종료

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Claude error (turn {turn}): {error_msg}")
            if "overloaded" in error_msg.lower() and turn < 2:
                time.sleep(2)
                continue
            yield "잠시 후 다시 말씀해주세요."
            full_response = "오류"
            break
    conversation_history.append({"role": "assistant", "content": full_response})

    # 메모리에 턴 저장 (백그라운드로 사실 추출)
    if full_response and full_response != "오류":
        try:
            memory.add_turn(user_text, full_response)
        except Exception as e:
            logger.error(f"Memory add_turn error: {e}")


def ask_davis_sync(user_text: str) -> str:
    """텍스트 입력 → 전체 응답 텍스트 반환 (음성 없음).

    텔레그램 봇에서 사용. stream_claude를 완전히 소비.
    """
    chunks = []
    for token in stream_claude(user_text):
        chunks.append(token)
    return "".join(chunks).strip()


def warmup():
    """Claude/TTS 콜드스타트 제거 (백그라운드 daemon)."""
    def _warm():
        try:
            # Claude prompt cache 초기화 (시스템 프롬프트 캐싱)
            logger.info("Warmup: Claude cache priming...")
            client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": "."}],
            )
            logger.info("Warmup: Claude ready")

            # TTS 예열 (짧은 더미)
            try:
                tmp = tempfile.mktemp(suffix=".mp3")
                asyncio.run(
                    edge_tts.Communicate(".", TTS_VOICE, rate=TTS_RATE).save(tmp)
                )
                if os.path.exists(tmp):
                    os.unlink(tmp)
                logger.info("Warmup: TTS ready")
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Warmup error: {e}")

    threading.Thread(target=_warm, daemon=True).start()


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
        self._root.title("DAVIS-CC")
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
        tk.Label(tf, text="DAVIS-CC v5", fg="#E6EDF3", bg="#161B22", font=("Consolas", 9, "bold")).pack(side=tk.LEFT)

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
                    prefix = {"user": "나: ", "jarvis": "데비스: ", "system": ""}
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

    logger.info("=" * 50)
    logger.info("DAVIS-CC v5 Starting...")
    logger.info("=" * 50)

    # HUD
    hud = SimpleHUD()
    hud.start()
    hud.dialog("system", "DAVIS-CC v5 시작 중...")

    # TTS (edge-tts + pygame - mpv 불필요)
    logger.info("TTS: edge-tts + pygame.mixer")
    speak("데비스 준비 중입니다.")
    logger.info("TTS ready")

    # Claude 캐시 + TTS 워밍업 (백그라운드)
    warmup()

    # STT
    logger.info("Loading STT...")
    hud.status("STT 로딩 중...")
    recorder = AudioToTextRecorder(
        model=STT_MODEL,
        language=STT_LANGUAGE,
        post_speech_silence_duration=0.7,       # 한국어 조사 pause 흡수
        spinner=False,
        silero_sensitivity=0.05,                # 엄격 (RealtimeVoiceChat 실전값)
        silero_deactivity_detection=True,
        silero_use_onnx=True,                   # VAD 가속
        webrtc_sensitivity=2,
        min_length_of_recording=0.3,
        min_gap_between_recordings=0.15,
        initial_prompt=STT_INITIAL_PROMPT,      # 고유명사 힌트
        beam_size=3,                            # 지연 감소 (5→3)
        enable_realtime_transcription=False,
    )
    logger.info("STT ready")

    # 텔레그램 봇 시작 (있으면)
    telegram_bot = None
    try:
        from telegram_bot import DavisTelegramBot
        telegram_bot = DavisTelegramBot(
            on_message=ask_davis_sync,
            on_start_message="DAVIS v5 온라인. 명령을 기다립니다."
        )
        if telegram_bot.start():
            logger.info("Telegram bot online")
            hud.dialog("system", "텔레그램 봇 활성화")
        else:
            telegram_bot = None
    except Exception as e:
        logger.error(f"Telegram bot start error: {e}")

    hud.status("준비 완료 — 말씀하세요")
    hud.dialog("system", "준비 완료. '데비스' 호출하세요.")
    hud.led("idle")

    print()
    print("=" * 50)
    print("  DAVIS-CC v5 — 실시간 음성 AI 어시스턴트")
    print("  말씀하세요. 자동으로 음성을 감지합니다.")
    print("  '데비스'로 호출하거나 바로 질문하세요.")
    print("  Ctrl+C로 종료")
    print("=" * 50)
    print()

    # 웨이크워드 엄격 모드 (기본) — "데비스" 호출 시에만 반응
    wake_mode = True

    try:
        while True:
            # 1. 음성 감지
            hud.led("idle")
            hud.status("'데비스' 대기 중...")

            user_text = recorder.text()

            if not user_text or is_noise(user_text):
                continue

            # 너무 긴 텍스트 차단 (TV/배경 소음)
            if len(user_text) > 30:
                logger.debug(f"Too long ({len(user_text)} chars), skipping")
                continue

            logger.info(f"STT: '{user_text}'")

            # 웨이크워드 엄격 체크
            if not is_wake_word(user_text):
                continue  # 무시

            logger.info(f"WAKE detected: '{user_text}'")
            hud.dialog("system", "데비스 호출됨")

            # "데비스, 명령" 형식이면 바로 실행
            cmd_text = extract_command_after_wake(user_text)

            if cmd_text:
                user_text = cmd_text
                logger.info(f"Inline command: '{cmd_text}'")
            else:
                # 웨이크워드만 호출한 경우 — 띵! 후 명령 대기
                hud.status("말씀하세요...")
                hud.led("listen")
                speak("네")

                # 명령 대기 (최대 10초)
                cmd_text = recorder.text()
                if not cmd_text or is_noise(cmd_text):
                    hud.status("'데비스' 대기 중...")
                    hud.led("idle")
                    continue
                if is_wake_word(cmd_text):
                    # 웨이크워드만 또 외친 경우
                    continue
                user_text = cmd_text

            # 2. 사용자 입력 표시
            hud.dialog("user", user_text)
            hud.led("think")
            hud.status("생각 중...")
            logger.info(f"User: {user_text}")
            print(f"\n>>> {user_text}")

            t0 = time.time()

            # 3. Claude 스트리밍 → 문장 단위 즉시 TTS
            hud.led("speak")
            hud.status("응답 중...")

            token_gen = stream_claude(user_text)
            speak_streaming(token_gen)

            elapsed = time.time() - t0

            # 4. 응답 표시
            if conversation_history:
                response = conversation_history[-1]["content"]
                hud.dialog("jarvis", response[:200])
                logger.info(f"DAVIS ({elapsed:.1f}s): {response[:100]}...")
                print(f"<<< {response}")

            hud.led("idle")
            hud.status("듣는 중...")

    except KeyboardInterrupt:
        print("\nDAVIS 종료...")
    finally:
        recorder.shutdown()
        pygame.mixer.quit()
        logger.info("DAVIS stopped")


if __name__ == "__main__":
    main()
