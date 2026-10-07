from __future__ import annotations

import os
import threading
from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Callable, Sequence
from urllib.parse import urlsplit, urlunsplit

from ..models import ActionRequest, ActionResult
from .privacy import redact_text


_PROCESS_APPS = {
    "brave.exe": "Brave",
    "chrome.exe": "Chrome",
    "msedge.exe": "Edge",
    "firefox.exe": "Firefox",
    "explorer.exe": "File Explorer",
    "chatgpt.exe": "ChatGPT",
    "whatsapp.exe": "WhatsApp",
    "spotify.exe": "Spotify",
    "code.exe": "Visual Studio Code",
    "notepad.exe": "Notepad",
    "windowsterminal.exe": "Windows Terminal",
    "powershell.exe": "PowerShell",
    "pwsh.exe": "PowerShell",
    "cmd.exe": "Command Prompt",
    "zoom.exe": "Zoom",
    "teams.exe": "Microsoft Teams",
    "ms-teams.exe": "Microsoft Teams",
    "winword.exe": "Microsoft Word",
    "excel.exe": "Microsoft Excel",
    "powerpnt.exe": "Microsoft PowerPoint",
    "outlook.exe": "Microsoft Outlook",
}
_BROWSERS = {"Brave", "Chrome", "Edge", "Firefox"}
_BROWSER_SUFFIXES = (
    " - Brave",
    " - Google Chrome",
    " - Microsoft Edge",
    " — Mozilla Firefox",
    " - Mozilla Firefox",
)


@dataclass(frozen=True, slots=True)
class WorkspaceWindow:
    app: str
    title: str
    foreground: bool = False
    safe_url: str = ""


@dataclass(frozen=True, slots=True)
class BrowserActivity:
    browser: str
    action: str
    description: str
    success: bool
    created_at: datetime


class CurrentWorkspace:
    """Ephemeral view of user-facing windows and Aksh browser activity."""

    def __init__(self):
        self._windows: list[WorkspaceWindow] = []
        self._activities: deque[BrowserActivity] = deque(maxlen=20)
        self._lock = threading.RLock()

    def refresh(
        self,
        observer: Callable[[], list[WorkspaceWindow]] | None = None,
    ) -> list[WorkspaceWindow]:
        scan = observer or observe_desktop
        try:
            windows = scan()
        except Exception:
            return self.windows()
        with self._lock:
            self._windows = list(windows)
            return list(self._windows)

    def record_action(self, action: ActionRequest, result: ActionResult) -> None:
        browser = self._browser_for(action)
        if not browser:
            return
        activity = BrowserActivity(
            browser=browser,
            action=action.name,
            description=redact_text(result.message, maximum=240),
            success=bool(result.success),
            created_at=datetime.now().astimezone(),
        )
        with self._lock:
            self._activities.append(activity)

    def enrich_actions(
        self, actions: Sequence[ActionRequest]
    ) -> list[ActionRequest]:
        enriched: list[ActionRequest] = []
        for action in actions:
            target = str(action.parameters.get("target", "")).strip()
            if action.name == "open_app" and self.is_open(target):
                enriched.append(ActionRequest("switch_window", {"target": target}))
            else:
                enriched.append(action)
        return enriched

    def is_open(self, target: str) -> bool:
        wanted = _canonical(target)
        if not wanted:
            return False
        with self._lock:
            return any(
                wanted == _canonical(window.app)
                or wanted in _canonical(window.title)
                for window in self._windows
            )

    def windows(self) -> list[WorkspaceWindow]:
        with self._lock:
            return list(self._windows)

    def activities(self) -> list[BrowserActivity]:
        with self._lock:
            return list(self._activities)

    def decision_context(self) -> str:
        with self._lock:
            windows = list(self._windows)
            activities = list(self._activities)[-8:]
        if not windows and not activities:
            return "No supported user-facing applications detected."
        lines: list[str] = []
        apps = sorted({window.app for window in windows})
        if apps:
            lines.append("Open applications: " + ", ".join(apps))
        for window in windows[:12]:
            focus = "foreground" if window.foreground else "visible"
            detail = f"- {window.app} ({focus}): {window.title}"
            if window.safe_url:
                detail += f" [{window.safe_url}]"
            lines.append(detail)
        if activities:
            lines.append("Recent Aksh browser activity:")
            lines.extend(
                f"- {item.browser}: {item.action}; success={item.success}; "
                f"{item.description}"
                for item in activities
            )
        return "\n".join(lines)

    def spoken_summary(self) -> str:
        with self._lock:
            windows = list(self._windows)
        if not windows:
            return "Current workspace mein supported open app detect nahi hui."
        grouped: dict[str, list[str]] = {}
        for window in windows:
            grouped.setdefault(window.app, [])
            if window.title not in grouped[window.app]:
                grouped[window.app].append(window.title)
        parts = []
        for app, titles in grouped.items():
            detail = f": {', '.join(titles[:2])}" if titles else ""
            parts.append(f"{app}{detail}")
        return "Current workspace mein " + "; ".join(parts) + " open hai."

    def clear(self) -> None:
        with self._lock:
            self._windows.clear()
            self._activities.clear()

    def _browser_for(self, action: ActionRequest) -> str:
        if action.name == "youtube_play":
            return _browser_label(action.parameters.get("target"))
        if action.name == "open_website":
            return _browser_label(action.parameters.get("browser"))
        if action.name == "open_app":
            return _browser_label(action.parameters.get("target"))
        if action.name not in {
            "browser_control",
            "youtube_control",
            "google_search",
            "download_current_video",
        }:
            return ""
        with self._lock:
            active = next(
                (window.app for window in self._windows if window.foreground),
                "",
            )
        return active if active in _BROWSERS else "Current browser"


def observe_desktop() -> list[WorkspaceWindow]:
    if os.name != "nt":
        return []
    import psutil
    import win32gui
    import win32process

    foreground = win32gui.GetForegroundWindow()
    windows: list[WorkspaceWindow] = []

    def collect(hwnd, _extra) -> None:
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = " ".join(win32gui.GetWindowText(hwnd).split())
        if not title:
            return
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process_name = psutil.Process(pid).name().casefold()
        except (psutil.Error, OSError):
            return
        app = _PROCESS_APPS.get(process_name)
        if not app:
            if "chatgpt" in title.casefold():
                app = "ChatGPT"
            else:
                return
        if app == "File Explorer" and win32gui.GetClassName(hwnd) not in {
            "CabinetWClass",
            "ExploreWClass",
        }:
            return
        windows.append(
            WorkspaceWindow(
                app=app,
                title=_clean_title(title),
                foreground=hwnd == foreground,
            )
        )

    win32gui.EnumWindows(collect, None)
    active_index = next(
        (
            index
            for index, window in enumerate(windows)
            if window.foreground and window.app in _BROWSERS
        ),
        None,
    )
    if active_index is not None and win32gui.GetForegroundWindow() == foreground:
        try:
            from ..capabilities.media import active_browser_url

            safe_url = sanitize_url(active_browser_url())
            windows[active_index] = replace(windows[active_index], safe_url=safe_url)
        except Exception:
            pass
    return windows


def sanitize_url(value: str) -> str:
    raw = str(value or "").strip()
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    host = parsed.hostname
    if parsed.port:
        host += f":{parsed.port}"
    path = parsed.path[:160]
    return urlunsplit((parsed.scheme, host, path, "", ""))


def _clean_title(title: str) -> str:
    cleaned = title
    for suffix in _BROWSER_SUFFIXES:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    return redact_text(cleaned, maximum=180) or "Untitled window"


def _browser_label(value: object) -> str:
    canonical = _canonical(value)
    labels = {"brave": "Brave", "chrome": "Chrome", "edge": "Edge", "firefox": "Firefox"}
    return labels.get(canonical, "")


def _canonical(value: object) -> str:
    return "".join(character for character in str(value or "").casefold() if character.isalnum())
