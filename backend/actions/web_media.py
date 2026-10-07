from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any

import requests

from ..models import ActionRequest, ActionResult
from .base import ActionGroup
from .browser_detection import (
    active_browser_name,
    default_browser_name,
    find_browser_executable,
    is_active_browser_window,
)


LOGGER = logging.getLogger(__name__)

WEBSITES = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "whatsapp": "https://web.whatsapp.com",
    "spotify": "https://open.spotify.com",
    "instagram": "https://instagram.com",
    "facebook": "https://facebook.com",
    "linkedin": "https://linkedin.com",
    "chatgpt": "https://chatgpt.com",
    "gmail": "https://mail.google.com",
    "drive": "https://drive.google.com",
    "meet": "https://meet.google.com",
    "calendar": "https://calendar.google.com",
    "canva": "https://canva.com",
    "notion": "https://notion.so",
}

class WebMediaActions(ActionGroup):
    def __init__(self, settings):
        super().__init__(settings)
        self._last_youtube_query: str | None = None
        self._last_youtube_browser: str | None = None

    def followup(self, text: str) -> ActionRequest | None:
        normalized = " ".join(str(text or "").lower().split())
        if not normalized or not self._last_youtube_query:
            return None
        if normalized in {
            "play this song",
            "this song",
            "play this",
            "yeh song",
            "yeh gaaen",
            "yeh gaana",
            "same song",
            "this one",
            "phir se chalao",
            "phir se bajao",
            "again play this song",
            "again play this",
        }:
            action = {"query": self._last_youtube_query}
            if self._last_youtube_browser:
                action["target"] = self._last_youtube_browser
            return ActionRequest("youtube_play", action)
        if normalized in {
            "play another song",
            "another song",
            "next song",
            "aur ek song",
            "next wala song",
        }:
            return ActionRequest("youtube_control", {"option": "next"})
        return None

    def open_website(self, parameters: dict[str, Any]) -> ActionResult:
        target = self.required(parameters, "target").lower().strip()
        browser_name = str(parameters.get("browser", "")).strip().lower()
        target = target.replace(" website", "").replace(" site", "").strip()
        url = WEBSITES.get(target)
        if not url:
            cleaned = re.sub(r"[^a-z0-9.-]", "", target)
            url = (
                f"https://{cleaned}"
                if "." in cleaned
                else f"https://www.google.com/search?q={urllib.parse.quote(target)}"
            )
        opened, used_browser = self._open_url(url, browser_name)
        if not opened:
            return ActionResult(
                False,
                f"{used_browser} browser is computer par nahi mila.",
            )
        location = f" {used_browser} mein" if used_browser else ""
        return ActionResult(True, f"{target}{location} open kar raha hoon.")

    def google_search(self, parameters: dict[str, Any]) -> ActionResult:
        query = self.required(parameters, "query")
        webbrowser.open(
            f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
        )
        return ActionResult(True, f"{query} search kar raha hoon.")

    def youtube_play(self, parameters: dict[str, Any]) -> ActionResult:
        query = self.required(parameters, "query")
        browser_name = str(parameters.get("target", "")).strip().lower()
        if not browser_name and self._last_youtube_browser:
            browser_name = self._last_youtube_browser
        video_url = self._resolve_youtube_video_url(query)
        if video_url:
            opened, used_browser = self._open_url(
                video_url,
                browser_name,
                try_reuse_tab=True,
            )
            if not opened:
                return ActionResult(
                    False,
                    f"{used_browser} browser is computer par nahi mila.",
                )
            self._last_youtube_query = query
            played_browser = browser_name or used_browser.casefold()
            if played_browser:
                self._last_youtube_browser = played_browser
            location = f"{used_browser} mein" if used_browser else "YouTube par"
            return ActionResult(True, f"{location} {query} play kar raha hoon.")

        search_url = (
            "https://www.youtube.com/results?search_query="
            + urllib.parse.quote_plus(query)
        )
        opened, used_browser = self._open_url(search_url, browser_name)
        if not opened:
            return ActionResult(
                False,
                f"{used_browser} browser is computer par nahi mila.",
            )
        self._last_youtube_query = query
        played_browser = browser_name or used_browser.casefold()
        if played_browser:
            self._last_youtube_browser = played_browser
        return ActionResult(
            False,
            f"{query} ka playable result resolve nahi hua. "
            "YouTube search results khol diye hain.",
        )

    def spotify_play(self, parameters: dict[str, Any]) -> ActionResult:
        query = self.required(parameters, "query")
        webbrowser.open(
            "https://open.spotify.com/search/" + urllib.parse.quote(query, safe="")
        )
        return ActionResult(True, f"Spotify par {query} dhoondh raha hoon.")

    def internet_speed(self, parameters: dict[str, Any]) -> ActionResult:
        started = time.perf_counter()
        response = requests.get(
            "https://speed.cloudflare.com/__down?bytes=5000000", timeout=20
        )
        response.raise_for_status()
        elapsed = max(0.001, time.perf_counter() - started)
        mbps = len(response.content) * 8 / elapsed / 1_000_000
        return ActionResult(True, f"Approximate download speed {mbps:.1f} Mbps hai.")

    def download_current_video(self, parameters: dict[str, Any]) -> ActionResult:
        from ..capabilities.media import active_browser_url, download_video

        url = active_browser_url()
        if not url or not str(url).startswith("http"):
            return ActionResult(False, "Active browser mein valid video URL nahi mila.")
        folder = Path.home() / "Downloads"
        threading.Thread(
            target=download_video,
            args=(url, str(folder)),
            name="aksh-download",
            daemon=True,
        ).start()
        return ActionResult(True, "Video download start ho gaya.")

    @staticmethod
    def _resolve_youtube_video_url(query: str) -> str | None:
        """Resolve the first real YouTube result without opening a search page."""
        try:
            from yt_dlp import YoutubeDL

            options = {
                "extract_flat": True,
                "noplaylist": True,
                "playlistend": 1,
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": 15,
            }
            with YoutubeDL(options) as downloader:
                result = downloader.extract_info(
                    f"ytsearch1:{query}",
                    download=False,
                )
            entries = result.get("entries") if isinstance(result, dict) else None
            first = entries[0] if entries else None
            if not isinstance(first, dict):
                return None
            video_id = str(first.get("id", "")).strip()
            if not re.fullmatch(r"[\w-]{11}", video_id):
                return None
            return f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
        except Exception as exc:
            LOGGER.warning("YouTube result resolution failed: %s", exc)
            return None

    @classmethod
    def _open_url(
        cls,
        url: str,
        browser_name: str = "",
        *,
        try_reuse_tab: bool = False,
    ) -> tuple[bool, str]:
        normalized = browser_name.replace(" browser", "").strip().lower()
        if not normalized:
            if try_reuse_tab and cls._is_youtube_url(url) and cls._reuse_active_youtube_tab(
                url
            ):
                reused_browser = active_browser_name()
                used_browser = reused_browser.title() if reused_browser else ""
                return True, used_browser
            webbrowser.open(url, new=0)
            detected_browser = default_browser_name()
            used_browser = detected_browser.title() if detected_browser else ""
            return True, used_browser
        executable = cls._find_browser_executable(normalized)
        if executable is None:
            return False, normalized.title()
        if try_reuse_tab and cls._reuse_active_youtube_tab(url, browser_name=normalized):
            return True, normalized.title()
        subprocess.Popen([str(executable), url])
        return True, normalized.title()

    @staticmethod
    def _find_browser_executable(browser_name: str) -> Path | None:
        return find_browser_executable(browser_name)

    @staticmethod
    def _is_youtube_url(url: str) -> bool:
        normalized = str(url).lower()
        return "youtube.com" in normalized or "youtu.be" in normalized

    @classmethod
    def _reuse_active_youtube_tab(
        cls,
        url: str,
        browser_name: str | None = None,
    ) -> bool:
        """Reuse an existing YouTube tab in the focused browser window.

        Chromium's tab search lets a user keep working in another tab while Aksh
        routes the next media request back to the existing YouTube tab.
        """
        if not cls._is_youtube_url(url):
            return False
        focused_browser = active_browser_name()
        if browser_name and focused_browser != browser_name:
            try:
                from ..capabilities.windows import switch_to_app

                if not switch_to_app(browser_name):
                    return False
                time.sleep(0.3)
                focused_browser = active_browser_name()
                if focused_browser != browser_name:
                    return False
            except Exception:
                LOGGER.debug(
                    "Could not focus the previous YouTube browser",
                    exc_info=True,
                )
                return False
        if not focused_browser:
            return False
        try:
            from ..capabilities.media import active_browser_url
            import pyautogui

            if focused_browser in {"brave", "chrome", "edge"}:
                pyautogui.hotkey("ctrl", "shift", "a")
                time.sleep(0.15)
                pyautogui.write("youtube", interval=0.02)
                time.sleep(0.15)
                pyautogui.press("enter")
                time.sleep(0.2)
                current = active_browser_url()
                if not current or not cls._is_youtube_url(current):
                    return False
            else:
                current = active_browser_url()
                if not current or not cls._is_youtube_url(current):
                    return False
            pyautogui.hotkey("ctrl", "l")
            time.sleep(0.08)
            pyautogui.write(url, interval=0.01)
            pyautogui.press("enter")
            return True
        except Exception:
            LOGGER.debug("Could not reuse active YouTube tab", exc_info=True)
            return False

    @staticmethod
    def _is_active_browser_window(browser_name: str) -> bool:
        return is_active_browser_window(browser_name)
