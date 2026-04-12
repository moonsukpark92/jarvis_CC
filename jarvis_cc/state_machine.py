"""상태 머신 — JARVIS-CC 시스템 상태 전이 관리.

상태: IDLE → ACTIVATING → LISTENING → PROCESSING → SPEAKING → IDLE
"""

import logging
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class State(Enum):
    IDLE = "idle"
    ACTIVATING = "activating"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


class Event(Enum):
    WAKE = "wake"           # 웨이크워드 감지 or 핫키
    READY = "ready"         # 활성화 시퀀스 완료
    COMMAND = "command"     # 음성 명령 입력 완료
    RESPONSE = "response"   # Claude Code 응답 감지
    DONE = "done"           # TTS 낭독 완료
    ABORT = "abort"         # ESC or 중단 명령


# 상태 전이 테이블
TRANSITIONS: dict[tuple[State, Event], State] = {
    (State.IDLE, Event.WAKE): State.ACTIVATING,
    (State.ACTIVATING, Event.READY): State.LISTENING,
    (State.LISTENING, Event.COMMAND): State.PROCESSING,
    (State.PROCESSING, Event.RESPONSE): State.SPEAKING,
    (State.SPEAKING, Event.DONE): State.IDLE,
    # ABORT: 어느 상태에서든 IDLE로 복귀
    (State.ACTIVATING, Event.ABORT): State.IDLE,
    (State.LISTENING, Event.ABORT): State.IDLE,
    (State.PROCESSING, Event.ABORT): State.IDLE,
    (State.SPEAKING, Event.ABORT): State.IDLE,
    # IDLE에서 RESPONSE가 오면 바로 SPEAKING (지속 모니터링)
    (State.IDLE, Event.RESPONSE): State.SPEAKING,
}


class JarvisStateMachine:
    """상태 머신 + 이벤트 콜백."""

    def __init__(self):
        self._state = State.IDLE
        self._callbacks: dict[str, list[Callable]] = {}
        self._on_transition: Optional[Callable[[State, Event, State], None]] = None

    @property
    def state(self) -> State:
        return self._state

    @property
    def state_name(self) -> str:
        return self._state.value

    def on_transition(self, callback: Callable[[State, Event, State], None]):
        """상태 전이 시 콜백 등록."""
        self._on_transition = callback

    def on_enter(self, state: State, callback: Callable[[], None]):
        """특정 상태 진입 시 콜백 등록."""
        key = f"enter_{state.value}"
        if key not in self._callbacks:
            self._callbacks[key] = []
        self._callbacks[key].append(callback)

    def on_exit(self, state: State, callback: Callable[[], None]):
        """특정 상태 퇴장 시 콜백 등��."""
        key = f"exit_{state.value}"
        if key not in self._callbacks:
            self._callbacks[key] = []
        self._callbacks[key].append(callback)

    def trigger(self, event: Event) -> bool:
        """이벤트 트리거 → 상태 전이."""
        key = (self._state, event)
        new_state = TRANSITIONS.get(key)

        if new_state is None:
            logger.debug(f"No transition: {self._state.value} + {event.value}")
            return False

        old_state = self._state

        # exit 콜백
        self._fire_callbacks(f"exit_{old_state.value}")

        # 전이
        self._state = new_state
        logger.info(f"State: {old_state.value} --[{event.value}]--> {new_state.value}")

        # transition 콜백
        if self._on_transition:
            try:
                self._on_transition(old_state, event, new_state)
            except Exception as e:
                logger.error(f"Transition callback error: {e}")

        # enter 콜백
        self._fire_callbacks(f"enter_{new_state.value}")

        return True

    def reset(self):
        """IDLE로 강제 리셋."""
        old = self._state
        self._state = State.IDLE
        if old != State.IDLE:
            logger.info(f"State reset: {old.value} --> idle")

    def _fire_callbacks(self, key: str):
        for cb in self._callbacks.get(key, []):
            try:
                cb()
            except Exception as e:
                logger.error(f"Callback error ({key}): {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    sm = JarvisStateMachine()
    sm.on_transition(lambda old, ev, new: print(f"  [{old.value}] --{ev.value}--> [{new.value}]"))

    print("[state_machine] Testing state transitions:")
    print(f"  Current: {sm.state_name}")

    sm.trigger(Event.WAKE)
    sm.trigger(Event.READY)
    sm.trigger(Event.COMMAND)
    sm.trigger(Event.RESPONSE)
    sm.trigger(Event.DONE)

    print(f"\n  Final: {sm.state_name}")

    print("\n[state_machine] Testing ABORT from PROCESSING:")
    sm.trigger(Event.WAKE)
    sm.trigger(Event.READY)
    sm.trigger(Event.COMMAND)
    sm.trigger(Event.ABORT)
    print(f"  After abort: {sm.state_name}")
    print("[state_machine] OK")
