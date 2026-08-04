from __future__ import annotations

import ctypes
import logging
import time


LOGGER = logging.getLogger(__name__)

WINDOW_ALIASES = {
    "code": "visual studio code",
    "vs code": "visual studio code",
    "tvs": "visual studio code",
    "brave": "brave",
    "chrome": "chrome",
    "whatsapp": "whatsapp",
    "notepad": "notepad",
    "terminal": "powershell",
}


def switch_to_app(app_name: str) -> bool:
    """Activate the first visible window matching a spoken app name."""
    import pyautogui
    import pygetwindow

    target = app_name.casefold().strip()
    if not target:
        return False
    target = next(
        (alias for phrase, alias in WINDOW_ALIASES.items() if phrase in target),
        target,
    )
    window = next(
        (
            item
            for item in pygetwindow.getAllWindows()
            if item.title and target in item.title.casefold()
        ),
        None,
    )
    if not window:
        return False
    try:
        if window.isMinimized:
            ctypes.windll.user32.ShowWindow(window._hWnd, 9)
            time.sleep(0.2)
        pyautogui.press("alt")
        window.activate()
        return True
    except Exception as exc:
        if "Error code from Windows: 0" in str(exc):
            return True
        LOGGER.warning("Could not switch to %s: %s", app_name, exc)
        return False
