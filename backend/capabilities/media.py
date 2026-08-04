from __future__ import annotations

import logging
import time
from pathlib import Path


LOGGER = logging.getLogger(__name__)


def active_browser_url() -> str:
    """Read the focused browser URL and restore the previous clipboard."""
    import pyautogui
    import pyperclip

    previous = pyperclip.paste()
    try:
        pyautogui.hotkey("alt", "d")
        time.sleep(0.15)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.15)
        return str(pyperclip.paste()).strip()
    finally:
        pyautogui.press("esc")
        try:
            pyperclip.copy(previous)
        except Exception:
            LOGGER.debug("Clipboard could not be restored", exc_info=True)


def download_video(url: str, folder: Path) -> str | None:
    import yt_dlp

    if not url.casefold().startswith(("http://", "https://")):
        return None
    folder.mkdir(parents=True, exist_ok=True)
    options = {
        "format": "best",
        "outtmpl": str(folder / "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
    }
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=True)
        return str(info.get("title", "video")) if info else "video"
    except Exception:
        LOGGER.exception("Video download failed for %s", url)
        return None
