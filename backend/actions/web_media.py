from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any

import requests

from ..models import ActionResult
from .base import ActionGroup


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


class WebMediaActions(ActionGroup):
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
        video_url = self._resolve_youtube_video_url(query)
        if video_url:
            opened, used_browser = self._open_url(video_url, browser_name)
            if not opened:
                return ActionResult(
                    False,
                    f"{used_browser} browser is computer par nahi mila.",
                )
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
    ) -> tuple[bool, str]:
        normalized = browser_name.replace(" browser", "").strip().lower()
        if not normalized:
            webbrowser.open(url)
            return True, ""
        executable = cls._find_browser_executable(normalized)
        if executable is None:
            return False, normalized.title()
        subprocess.Popen([str(executable), url])
        return True, normalized.title()

    @staticmethod
    def _find_browser_executable(browser_name: str) -> Path | None:
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
