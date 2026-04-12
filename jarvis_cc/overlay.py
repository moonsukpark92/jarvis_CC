"""HUD 오버레이 — tkinter topmost 반투명 패널.

화면 우하단에 상태/대화 표시. 드래그 이동 가능.
"""

import logging
import queue
import threading
import tkinter as tk
from tkinter import font as tkfont
from typing import Optional

from jarvis_cc.config import HUDConfig

logger = logging.getLogger(__name__)

# 상태별 LED 색상
STATE_COLORS = {
    "idle": "#6E7681",
    "activating": "#FFD700",
    "listening": "#FFD700",
    "processing": "#00B4FF",
    "speaking": "#3FB950",
    "error": "#F85149",
}


class HUDOverlay:
    """320x400 반투명 HUD 패널."""

    def __init__(self, config: HUDConfig):
        self.config = config
        self._root: Optional[tk.Tk] = None
        self._state_label: Optional[tk.Label] = None
        self._state_led: Optional[tk.Canvas] = None
        self._dialog_text: Optional[tk.Text] = None
        self._command_queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._current_state = "idle"

    def start(self):
        """HUD 오버레이 시작 (별도 스레드)."""
        if not self.config.enabled:
            logger.info("HUD overlay disabled")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_tk, daemon=True)
        self._thread.start()
        logger.info("HUD overlay started")

    def stop(self):
        """HUD 오버레이 중단."""
        self._running = False
        self._enqueue("destroy")
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("HUD overlay stopped")

    def update_state(self, state: str):
        """상태 업데이트 (LED 색상 변경)."""
        self._current_state = state
        self._enqueue("state", state)

    def append_dialog(self, role: str, text: str):
        """대화 로그 추가."""
        self._enqueue("dialog", role, text)

    def show(self):
        self._enqueue("show")

    def hide(self):
        self._enqueue("hide")

    def _enqueue(self, cmd: str, *args):
        self._command_queue.put((cmd, args))

    def _run_tk(self):
        """tkinter 메인루프 (별도 스레드에서 실행)."""
        self._root = tk.Tk()
        self._root.title("JARVIS-CC")

        # 반투명 + 항상 위
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        try:
            self._root.attributes("-alpha", self.config.opacity)
        except tk.TclError:
            pass

        bg = self.config.theme_bg
        accent = self.config.theme_accent
        text_color = self.config.theme_text

        # 위치: 화면 우하단
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        x = screen_w - self.config.width - 20
        y = screen_h - self.config.height - 60
        self._root.geometry(f"{self.config.width}x{self.config.height}+{x}+{y}")
        self._root.configure(bg=bg)

        # ─── 타이틀 바 ───
        title_frame = tk.Frame(self._root, bg="#161B22", height=30)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        # LED
        self._state_led = tk.Canvas(
            title_frame, width=12, height=12, bg="#161B22", highlightthickness=0
        )
        self._state_led.pack(side=tk.LEFT, padx=(8, 4), pady=9)
        self._led_item = self._state_led.create_oval(2, 2, 10, 10, fill=STATE_COLORS["idle"])

        # 타이틀
        title_label = tk.Label(
            title_frame, text="JARVIS-CC", fg=text_color, bg="#161B22",
            font=("Consolas", 10, "bold"),
        )
        title_label.pack(side=tk.LEFT)

        # 닫기 버튼 (트레이로 최소화)
        close_btn = tk.Label(
            title_frame, text="×", fg="#8B949E", bg="#161B22",
            font=("Consolas", 14), cursor="hand2",
        )
        close_btn.pack(side=tk.RIGHT, padx=8)
        close_btn.bind("<Button-1>", lambda e: self.hide())

        # 최소화 버튼
        min_btn = tk.Label(
            title_frame, text="─", fg="#8B949E", bg="#161B22",
            font=("Consolas", 10), cursor="hand2",
        )
        min_btn.pack(side=tk.RIGHT, padx=4)
        min_btn.bind("<Button-1>", lambda e: self.hide())

        # 드래그 이동
        self._drag_data = {"x": 0, "y": 0}
        title_frame.bind("<Button-1>", self._on_drag_start)
        title_frame.bind("<B1-Motion>", self._on_drag_motion)
        title_label.bind("<Button-1>", self._on_drag_start)
        title_label.bind("<B1-Motion>", self._on_drag_motion)

        # ─── 상태 표시 ───
        self._state_label = tk.Label(
            self._root, text="상태: ● 대기 중", fg=text_color, bg=bg,
            font=("맑은 고딕", 9), anchor=tk.W,
        )
        self._state_label.pack(fill=tk.X, padx=10, pady=(8, 4))

        # 구분선
        tk.Frame(self._root, bg="#30363D", height=1).pack(fill=tk.X, padx=10)

        # ─── 대화 로그 ───
        dialog_label = tk.Label(
            self._root, text="[대화 로그]", fg="#8B949E", bg=bg,
            font=("맑은 고딕", 8), anchor=tk.W,
        )
        dialog_label.pack(fill=tk.X, padx=10, pady=(6, 2))

        self._dialog_text = tk.Text(
            self._root, bg="#0D1117", fg=text_color,
            font=("맑은 고딕", 9), wrap=tk.WORD,
            highlightthickness=0, borderwidth=0,
            insertbackground=text_color, selectbackground=accent,
            state=tk.DISABLED, padx=8, pady=4,
        )
        self._dialog_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))

        # 태그 설정
        self._dialog_text.tag_configure("user", foreground="#58A6FF")
        self._dialog_text.tag_configure("jarvis", foreground="#3FB950")
        self._dialog_text.tag_configure("system", foreground="#8B949E")

        # ─── 커맨드 처리 루프 ───
        self._process_commands()
        self._root.mainloop()

    def _process_commands(self):
        """큐에서 커맨드를 꺼내 실행."""
        if not self._running and self._root:
            try:
                self._root.destroy()
            except Exception:
                pass
            return

        try:
            while True:
                cmd, args = self._command_queue.get_nowait()
                if cmd == "destroy":
                    try:
                        self._root.destroy()
                    except tk.TclError:
                        pass
                    return
                elif cmd == "state":
                    self._do_update_state(args[0])
                elif cmd == "dialog":
                    self._do_append_dialog(args[0], args[1])
                elif cmd == "show":
                    self._root.deiconify()
                elif cmd == "hide":
                    self._root.withdraw()
        except queue.Empty:
            pass

        if self._root:
            self._root.after(100, self._process_commands)

    def _do_update_state(self, state: str):
        """상태 LED + 텍스트 업데이트."""
        if not self._root:
            return
        color = STATE_COLORS.get(state, STATE_COLORS["idle"])
        state_names = {
            "idle": "대기 중",
            "activating": "활성화 중",
            "listening": "듣는 중",
            "processing": "처리 중",
            "speaking": "말하는 중",
            "error": "오류",
        }
        name = state_names.get(state, state)

        if self._state_led:
            self._state_led.itemconfig(self._led_item, fill=color)
        if self._state_label:
            self._state_label.config(text=f"상태: ● {name}")

    def _do_append_dialog(self, role: str, text: str):
        """대화 로그에 텍스트 추가."""
        if not self._dialog_text or not self._root:
            return

        self._dialog_text.config(state=tk.NORMAL)

        prefix_map = {"user": "나: ", "jarvis": "자비스: ", "system": "시스템: "}
        tag = role if role in ("user", "jarvis", "system") else "system"
        prefix = prefix_map.get(role, "")

        self._dialog_text.insert(tk.END, f"{prefix}{text}\n", tag)
        self._dialog_text.see(tk.END)
        self._dialog_text.config(state=tk.DISABLED)

    def _on_drag_start(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag_motion(self, event):
        if self._root:
            dx = event.x - self._drag_data["x"]
            dy = event.y - self._drag_data["y"]
            x = self._root.winfo_x() + dx
            y = self._root.winfo_y() + dy
            self._root.geometry(f"+{x}+{y}")


if __name__ == "__main__":
    import time as _time

    logging.basicConfig(level=logging.INFO)
    config = HUDConfig()
    overlay = HUDOverlay(config)
    overlay.start()

    _time.sleep(1)
    overlay.update_state("activating")
    overlay.append_dialog("system", "JARVIS-CC 활성화")

    _time.sleep(1)
    overlay.update_state("listening")
    overlay.append_dialog("user", "파이썬 오류 찾아줘")

    _time.sleep(1)
    overlay.update_state("processing")

    _time.sleep(2)
    overlay.update_state("speaking")
    overlay.append_dialog("jarvis", "박대표님, 14번 줄 들여쓰기 오류입니다.")

    _time.sleep(2)
    overlay.update_state("idle")

    print("[overlay] Test running, Ctrl+C to stop")
    try:
        while True:
            _time.sleep(1)
    except KeyboardInterrupt:
        overlay.stop()
