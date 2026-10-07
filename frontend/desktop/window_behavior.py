from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes


LOGGER = logging.getLogger(__name__)
GA_ROOT = 2
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TRANSPARENT = 0x00000020
WS_EX_APPWINDOW = 0x00040000
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020


def _window_handle(widget) -> int:
    widget.update_idletasks()
    child = int(widget.winfo_id())
    user32 = ctypes.windll.user32
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    return int(user32.GetAncestor(child, GA_ROOT) or child)


def hide_from_taskbar(widget) -> bool:
    """Give a Tk top-level the Windows tool-window taskbar behavior."""
    if sys.platform != "win32":
        return False
    try:
        hwnd = _window_handle(widget)
        user32 = ctypes.windll.user32
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.SetWindowLongW.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_long,
        ]
        user32.SetWindowLongW.restype = ctypes.c_long
        style = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE))
        desired = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        if desired != style:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, desired)
        _set_window_position(hwnd, insert_after=None, frame_changed=True)
        current = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE))
        return bool(current & WS_EX_TOOLWINDOW) and not bool(
            current & WS_EX_APPWINDOW
        )
    except Exception as exc:
        LOGGER.warning("Taskbar hiding unavailable: %s", exc)
        return False


def keep_always_on_top(widget) -> bool:
    """Keep a visible Tk window above normal Windows without taking focus."""
    try:
        widget.attributes("-topmost", True)
        widget.lift()
    except Exception as exc:
        LOGGER.warning("Tk always-on-top unavailable: %s", exc)
        return False
    if sys.platform != "win32":
        return True
    try:
        return _set_window_position(
            _window_handle(widget),
            insert_after=HWND_TOPMOST,
        )
    except Exception as exc:
        LOGGER.warning("Native always-on-top unavailable: %s", exc)
        return False


def set_click_through(widget, enabled: bool) -> bool:
    """Let pointer input pass through an invisible Windows overlay."""
    if sys.platform != "win32":
        return False
    try:
        hwnd = _window_handle(widget)
        user32 = ctypes.windll.user32
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.SetWindowLongW.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_long,
        ]
        user32.SetWindowLongW.restype = ctypes.c_long
        style = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE))
        desired = (
            style | WS_EX_TRANSPARENT
            if enabled
            else style & ~WS_EX_TRANSPARENT
        )
        if desired != style:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, desired)
            _set_window_position(hwnd, insert_after=None, frame_changed=True)
        current = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE))
        return bool(current & WS_EX_TRANSPARENT) is bool(enabled)
    except Exception as exc:
        LOGGER.warning("Click-through window style unavailable: %s", exc)
        return False


def _set_window_position(
    hwnd: int,
    *,
    insert_after: int | None,
    frame_changed: bool = False,
) -> bool:
    user32 = ctypes.windll.user32
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
    if insert_after is None:
        flags |= SWP_NOZORDER
    if frame_changed:
        flags |= SWP_FRAMECHANGED
    return bool(user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, flags))
