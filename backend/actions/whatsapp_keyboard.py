from __future__ import annotations

import time

import pyperclip
import win32api
import win32con


def _tap(key: int) -> None:
    win32api.keybd_event(key, 0, 0, 0)
    win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)


def _shortcut(modifier: int, key: int) -> None:
    win32api.keybd_event(modifier, 0, 0, 0)
    try:
        _tap(key)
    finally:
        win32api.keybd_event(
            modifier, 0, win32con.KEYEVENTF_KEYUP, 0
        )


def replace_focused_text(value: str) -> None:
    _shortcut(win32con.VK_CONTROL, ord("A"))
    time.sleep(0.05)
    if value:
        pyperclip.copy(value)
        _shortcut(win32con.VK_CONTROL, ord("V"))
    else:
        _tap(win32con.VK_BACK)


def press_enter() -> None:
    _tap(win32con.VK_RETURN)
