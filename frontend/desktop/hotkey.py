from __future__ import annotations

import logging
from typing import Callable


LOGGER = logging.getLogger(__name__)


class GlobalHotkey:
    def __init__(self, combination: str, callback: Callable[[], None]):
        self.combination = combination
        self.callback = callback
        self.listener = None

    def start(self) -> None:
        try:
            from pynput import keyboard

            hotkey = keyboard.HotKey(
                keyboard.HotKey.parse(self._pynput_expression()), self.callback
            )

            def canonical(function):
                return lambda key: function(listener.canonical(key))

            listener = keyboard.Listener(
                on_press=canonical(hotkey.press),
                on_release=canonical(hotkey.release),
            )
            self.listener = listener
            listener.start()
        except Exception as exc:
            LOGGER.warning("Global hotkey unavailable: %s", exc)

    def _pynput_expression(self) -> str:
        modifiers = {"ctrl", "alt", "shift", "cmd", "win"}
        tokens = [token.strip().lower() for token in self.combination.split("+")]
        normalized = [
            f"<{'cmd' if token == 'win' else token}>" if token in modifiers else token
            for token in tokens
            if token
        ]
        return "+".join(normalized)

    def close(self) -> None:
        if self.listener:
            self.listener.stop()
