from __future__ import annotations

import queue
import threading
from typing import Any


POINTER_ACTIONS = {
    "move",
    "down",
    "up",
    "click",
    "double_click",
    "right_click",
}
ALLOWED_KEYS = {
    "enter",
    "esc",
    "backspace",
    "delete",
    "tab",
    "space",
    "home",
    "end",
    "left",
    "right",
    "up",
    "down",
    "pageup",
    "pagedown",
    "alt_tab",
}


def normalize_input_event(value: dict[str, Any]) -> dict[str, Any]:
    action = str(value.get("action", "")).strip().lower()
    if action in POINTER_ACTIONS:
        return {
            "action": action,
            "x": _unit(value.get("x")),
            "y": _unit(value.get("y")),
        }
    if action == "scroll":
        delta = max(-12, min(12, int(value.get("delta", 0))))
        if not delta:
            raise ValueError("Scroll delta required.")
        return {"action": action, "delta": delta}
    if action == "text":
        text = str(value.get("text", ""))[:1000]
        if not text:
            raise ValueError("Text required.")
        return {"action": action, "text": text}
    if action == "key":
        key = str(value.get("key", "")).strip().lower()
        if key not in ALLOWED_KEYS:
            raise ValueError("Unsupported remote key.")
        return {"action": action, "key": key}
    raise ValueError("Unsupported remote input action.")


def _unit(value: object) -> float:
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError("Pointer coordinates must be between 0 and 1.")
    return number


class RemoteInputController:
    def __init__(self):
        self._events: queue.Queue[dict[str, Any] | None] = queue.Queue(256)
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def submit(self, value: dict[str, Any]) -> None:
        event = normalize_input_event(value)
        self._ensure_started()
        try:
            self._events.put_nowait(event)
        except queue.Full as exc:
            raise RuntimeError("Remote input queue busy.") from exc

    def release(self) -> None:
        if self._thread is None:
            return
        try:
            self._events.put_nowait({"action": "release"})
        except queue.Full:
            pass

    def close(self) -> None:
        if self._thread is not None:
            self._events.put(None)

    def _ensure_started(self) -> None:
        if self._thread is not None:
            return
        with self._lock:
            if self._thread is None:
                self._thread = threading.Thread(
                    target=self._run,
                    name="aksh-remote-input",
                    daemon=True,
                )
                self._thread.start()

    def _run(self) -> None:
        import pyautogui

        pyautogui.PAUSE = 0.01
        while True:
            event = self._events.get()
            if event is None:
                return
            try:
                self._execute(pyautogui, event)
            except Exception:
                continue

    @staticmethod
    def _execute(pyautogui, event: dict[str, Any]) -> None:
        action = event["action"]
        if action == "release":
            pyautogui.mouseUp()
            return
        if action in POINTER_ACTIONS:
            size = pyautogui.size()
            x = min(size.width - 1, round(event["x"] * size.width))
            y = min(size.height - 1, round(event["y"] * size.height))
            pyautogui.moveTo(x, y, duration=0.01)
            if action == "down":
                pyautogui.mouseDown()
            elif action == "up":
                pyautogui.mouseUp()
            elif action == "click":
                pyautogui.click()
            elif action == "double_click":
                pyautogui.doubleClick(interval=0.12)
            elif action == "right_click":
                pyautogui.rightClick()
            return
        if action == "scroll":
            pyautogui.scroll(event["delta"])
            return
        if action == "key":
            if event["key"] == "alt_tab":
                pyautogui.hotkey("alt", "tab")
            else:
                pyautogui.press(event["key"])
            return
        _paste_text(pyautogui, event["text"])


def _paste_text(pyautogui, text: str) -> None:
    import time

    import pyperclip

    previous = pyperclip.paste()
    try:
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.08)
    finally:
        pyperclip.copy(previous)
