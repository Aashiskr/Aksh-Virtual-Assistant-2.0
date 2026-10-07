from __future__ import annotations

import ctypes
import logging
import os
import sys
from ctypes import wintypes


LOGGER = logging.getLogger(__name__)
WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011
GA_ROOT = 2
MENU_WINDOW_CLASSES = {"MenuWindowClass", "EmbeddedMenuWindowClass"}


def set_capture_excluded(widget, excluded: bool = True) -> bool:
    """Hide this process-owned top-level window from supported capture APIs."""
    if sys.platform != "win32":
        return False
    try:
        widget.update_idletasks()
        child = int(widget.winfo_id())
        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        hwnd = int(user32.GetAncestor(child, GA_ROOT)) or child
        success = _set_window_capture_excluded(hwnd, excluded)
        if not success:
            error = ctypes.get_last_error()
            LOGGER.warning(
                "Screen-capture exclusion failed: hwnd=%s error=%s",
                hwnd,
                error,
            )
        return success
    except Exception as exc:
        LOGGER.warning("Screen-capture exclusion unavailable: %s", exc)
        return False


def exclude_popup_menus_from_capture() -> int:
    """Exclude this process's native Tk popup and submenu windows."""
    if sys.platform != "win32":
        return 0
    try:
        user32 = ctypes.windll.user32
        callback_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM,
        )
        user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        user32.GetClassNameW.argtypes = [
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        ]
        user32.GetClassNameW.restype = ctypes.c_int
        excluded = 0

        def visit(hwnd, _lparam):
            nonlocal excluded
            process_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(
                hwnd,
                ctypes.byref(process_id),
            )
            if process_id.value != os.getpid():
                return True
            class_name = ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(hwnd, class_name, len(class_name))
            if (
                class_name.value in MENU_WINDOW_CLASSES
                and _set_window_capture_excluded(int(hwnd), True)
            ):
                excluded += 1
            return True

        user32.EnumWindows(callback_type(visit), 0)
        return excluded
    except Exception as exc:
        LOGGER.warning("Popup-menu capture exclusion unavailable: %s", exc)
        return 0


def _set_window_capture_excluded(hwnd: int, excluded: bool) -> bool:
    user32 = ctypes.windll.user32
    user32.SetWindowDisplayAffinity.argtypes = [
        wintypes.HWND,
        wintypes.DWORD,
    ]
    user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
    affinity = WDA_EXCLUDEFROMCAPTURE if excluded else WDA_NONE
    return bool(user32.SetWindowDisplayAffinity(hwnd, affinity))
