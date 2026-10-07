from __future__ import annotations

import ctypes
import logging
import os
import shutil
from pathlib import Path


LOGGER = logging.getLogger(__name__)

_BROWSER_RELATIVE_PATHS = {
    "brave": ("BraveSoftware/Brave-Browser/Application/brave.exe",),
    "chrome": ("Google/Chrome/Application/chrome.exe",),
    "edge": ("Microsoft/Edge/Application/msedge.exe",),
    "firefox": ("Mozilla Firefox/firefox.exe",),
}
_BROWSER_COMMANDS = {
    "brave": ("brave.exe", "brave"),
    "chrome": ("chrome.exe", "chrome"),
    "edge": ("msedge.exe", "msedge"),
    "firefox": ("firefox.exe", "firefox"),
}
_BROWSER_TITLE_HINTS = {
    "brave": ("brave",),
    "chrome": ("chrome",),
    "edge": ("edge", "microsoft edge"),
    "firefox": ("firefox",),
}


def find_browser_executable(browser_name: str) -> Path | None:
    commands = _BROWSER_COMMANDS.get(browser_name)
    if not commands:
        return None
    for command in commands:
        found = shutil.which(command)
        if found:
            return Path(found)
    roots = [
        os.getenv("LOCALAPPDATA", ""),
        os.getenv("PROGRAMFILES", ""),
        os.getenv("PROGRAMFILES(X86)", ""),
    ]
    for root in filter(None, roots):
        for relative in _BROWSER_RELATIVE_PATHS[browser_name]:
            candidate = Path(root) / Path(relative)
            if candidate.is_file():
                return candidate
    return None


def default_browser_name() -> str | None:
    """Return the Windows browser registered for HTTPS links."""
    try:
        import winreg

        key_path = (
            r"Software\Microsoft\Windows\Shell\Associations"
            r"\UrlAssociations\https\UserChoice"
        )
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            prog_id = str(winreg.QueryValueEx(key, "ProgId")[0]).casefold()
        hints = (
            ("brave", "brave"),
            ("chrome", "chrome"),
            ("msedge", "edge"),
            ("microsoftedge", "edge"),
            ("firefox", "firefox"),
        )
        for token, name in hints:
            if token in prog_id:
                return name
    except Exception:
        LOGGER.debug("Could not determine the default HTTPS browser", exc_info=True)
    return None


def active_browser_name() -> str | None:
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return None
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return None
        text = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, text, length + 1)
        title = text.value.casefold()
        for name, candidates in _BROWSER_TITLE_HINTS.items():
            if any(token in title for token in candidates):
                return name
    except Exception:
        LOGGER.debug("Could not determine active browser window", exc_info=True)
    return None


def is_active_browser_window(browser_name: str) -> bool:
    normalized = browser_name.replace(" browser", "").strip().lower()
    if normalized not in _BROWSER_TITLE_HINTS:
        return True
    return active_browser_name() == normalized
