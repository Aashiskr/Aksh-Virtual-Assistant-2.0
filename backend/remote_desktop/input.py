from __future__ import annotations

import queue
import sys
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
PRESENTATION_COMMANDS = {
    "next",
    "previous",
    "zoom_in",
    "zoom_out",
    "zoom_reset",
}
PRESENTATION_ZOOM_COMMANDS = {
    "zoom_in",
    "zoom_out",
    "zoom_reset",
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


def normalize_presentation_command(value: object) -> str:
    command = str(value or "").strip().lower()
    if command not in PRESENTATION_COMMANDS:
        raise ValueError("Unsupported presentation command.")
    return command


def normalize_presentation_focus(
    x: object | None,
    y: object | None,
) -> tuple[float, float] | None:
    if x is None and y is None:
        return None
    if x is None or y is None:
        raise ValueError("Both presentation focus coordinates are required.")
    return (_unit(x), _unit(y))


def _unit(value: object) -> float:
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError("Pointer coordinates must be between 0 and 1.")
    return number


def _captured_monitor_bounds() -> tuple[int, int, int, int]:
    """Return the same monitor rectangle used by the screen capture stream."""
    import mss

    with mss.mss() as capture:
        monitor = capture.monitors[1]
        return (
            int(monitor["left"]),
            int(monitor["top"]),
            int(monitor["width"]),
            int(monitor["height"]),
        )


def _focused_monitor_coordinate(
    origin: int,
    length: int,
    normalized: float,
) -> int:
    local = min(length - 1, round(normalized * length))
    if length > 2:
        # PyAutoGUI's emergency fail-safe uses the exact screen corners.
        # Staying one pixel inside keeps edge-focused zoom responsive.
        local = max(1, min(length - 2, local))
    return origin + local


class RemoteInputController:
    def __init__(self):
        self._events: queue.Queue[dict[str, Any] | None] = queue.Queue(256)
        self._thread: threading.Thread | None = None
        self._start_lock = threading.Lock()
        self._generation_lock = threading.RLock()
        self._generation = 0

    def submit(self, value: dict[str, Any]) -> None:
        event = normalize_input_event(value)
        self._enqueue(event)

    def submit_presentation(
        self,
        command: object,
        *,
        x: object | None = None,
        y: object | None = None,
    ) -> None:
        normalized_command = normalize_presentation_command(command)
        focus = normalize_presentation_focus(x, y)
        if focus is not None and normalized_command not in PRESENTATION_ZOOM_COMMANDS:
            raise ValueError("Presentation focus is only supported for zoom actions.")
        event: dict[str, Any] = {
            "action": "presentation",
            "command": normalized_command,
        }
        if focus is not None:
            event.update({"x": focus[0], "y": focus[1]})
        self._enqueue(event)

    def _enqueue(self, event: dict[str, Any]) -> None:
        self._ensure_started()
        with self._generation_lock:
            event["_generation"] = self._generation
            try:
                self._events.put_nowait(event)
            except queue.Full as exc:
                raise RuntimeError("Remote input queue busy.") from exc

    def release(self) -> None:
        if self._thread is None:
            return
        try:
            self._enqueue({"action": "release"})
        except RuntimeError:
            pass

    def revoke(self) -> None:
        """Cancel queued events when a screen session loses ownership."""
        with self._generation_lock:
            self._generation += 1
            while True:
                try:
                    self._events.get_nowait()
                except queue.Empty:
                    break
            if self._thread is not None:
                self._events.put_nowait(
                    {"action": "release", "_generation": self._generation}
                )

    def close(self) -> None:
        if self._thread is not None:
            with self._generation_lock:
                self._generation += 1
                while True:
                    try:
                        self._events.get_nowait()
                    except queue.Empty:
                        break
                self._events.put_nowait(None)

    def _ensure_started(self) -> None:
        if self._thread is not None:
            return
        with self._start_lock:
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
            with self._generation_lock:
                if event.get("_generation") != self._generation:
                    continue
                try:
                    self._execute(pyautogui, event)
                except Exception:
                    continue

    @staticmethod
    def magnifier_running() -> bool:
        if sys.platform != "win32":
            return False
        try:
            import psutil

            return any(
                (process.info.get("name") or "").casefold() == "magnify.exe"
                for process in psutil.process_iter(["name"])
            )
        except Exception:
            return False

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
        if action == "presentation":
            command = normalize_presentation_command(event.get("command"))
            focus = normalize_presentation_focus(event.get("x"), event.get("y"))
            if focus is not None:
                if command not in PRESENTATION_ZOOM_COMMANDS:
                    raise ValueError(
                        "Presentation focus is only supported for zoom actions."
                    )
                left, top, width, height = _captured_monitor_bounds()
                x = _focused_monitor_coordinate(left, width, focus[0])
                y = _focused_monitor_coordinate(top, height, focus[1])
                pyautogui.moveTo(x, y, duration=0.01)
            if command == "next":
                pyautogui.press("pagedown")
            elif command == "previous":
                pyautogui.press("pageup")
            elif command == "zoom_in":
                pyautogui.hotkey("win", "+")
            elif command == "zoom_out":
                pyautogui.hotkey("win", "-")
            else:
                pyautogui.hotkey("win", "esc")
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
