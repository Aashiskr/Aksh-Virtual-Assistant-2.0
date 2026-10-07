from __future__ import annotations

import logging
import re
import subprocess
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .chrome_accounts import ChromeAccount, MeetingSchedulingError


LOGGER = logging.getLogger(__name__)
MEET_LINK_PATTERN = re.compile(
    r"https://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class MeetingDraft:
    title: str
    start: datetime
    end: datetime
    attendees: tuple[str, ...] = ()


class ChromeCalendarBrowser:
    """Create a Calendar event through the selected signed-in Chrome account."""

    def __init__(
        self,
        chrome_executable: Path,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.chrome_executable = chrome_executable
        self.sleep = sleep

    def schedule(self, account: ChromeAccount, draft: MeetingDraft) -> str:
        previous_windows = self._chrome_window_handles()
        subprocess.Popen(
            [
                str(self.chrome_executable),
                f"--profile-directory={account.profile_directory}",
                "--new-window",
                self.event_url(account, draft),
            ]
        )
        window = self._wait_for_calendar_window(previous_windows)
        window.set_focus()

        link = self._read_meet_link(window)
        if not link:
            add_meet = self._find_control(
                window,
                "add google meet video conferencing",
            )
            if add_meet is None:
                raise MeetingSchedulingError(
                    f"{account.label} account ka Calendar event khula, lekin "
                    "Google Meet option nahi mila. Account sign-in check karein."
                )
            add_meet.click_input()
            link = self._wait_for_meet_link(window)
        if not link:
            raise MeetingSchedulingError("Google Meet link generate nahi hua.")

        window.set_focus()
        save = self._find_control(window, "save", exact=True)
        if save is not None:
            save.click_input()
        else:
            import pyautogui

            pyautogui.hotkey("ctrl", "s")
        self.sleep(1.0)
        self._finish_invitation_dialog(window)
        return link

    @staticmethod
    def event_url(account: ChromeAccount, draft: MeetingDraft) -> str:
        start = draft.start.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        end = draft.end.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        parameters: list[tuple[str, str]] = [
            ("action", "TEMPLATE"),
            ("text", draft.title),
            ("dates", f"{start}/{end}"),
            ("details", "Scheduled by Aksh"),
        ]
        if account.email:
            parameters.append(("authuser", account.email))
        parameters.extend(("add", email) for email in draft.attendees)
        return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(
            parameters
        )

    def _wait_for_calendar_window(self, previous_handles: set[int]):
        try:
            from pywinauto import Desktop
        except ImportError as exc:
            raise MeetingSchedulingError(
                "Chrome Calendar automation ke liye pywinauto installed nahi hai."
            ) from exc
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            candidates = []
            for window in Desktop(backend="uia").windows():
                try:
                    handle = int(window.handle)
                    class_name = str(window.element_info.class_name or "")
                    if (
                        window.is_visible()
                        and class_name == "Chrome_WidgetWin_1"
                        and handle not in previous_handles
                    ):
                        candidates.append(window)
                except Exception:
                    continue
            if candidates:
                return candidates[-1]
            self.sleep(0.5)
        raise MeetingSchedulingError(
            "Selected Chrome profile ki nayi Calendar window open nahi hui."
        )

    @staticmethod
    def _chrome_window_handles() -> set[int]:
        try:
            from pywinauto import Desktop

            return {
                int(window.handle)
                for window in Desktop(backend="uia").windows()
                if str(window.element_info.class_name or "")
                == "Chrome_WidgetWin_1"
            }
        except Exception:
            return set()

    def _wait_for_meet_link(self, window) -> str:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            link = self._read_meet_link(window)
            if link:
                return link
            self.sleep(0.35)
        return ""

    def _read_meet_link(self, window) -> str:
        for control in self._controls(window):
            match = MEET_LINK_PATTERN.search(self._control_name(control))
            if match:
                return match.group(0)

        copy_button = self._find_control(window, "copy conference info")
        if copy_button is None:
            copy_button = self._find_control(window, "copy meeting info")
        if copy_button is None:
            return ""
        try:
            import pyperclip

            previous = pyperclip.paste()
            copy_button.click_input()
            self.sleep(0.25)
            copied = str(pyperclip.paste() or "")
            pyperclip.copy(previous)
            match = MEET_LINK_PATTERN.search(copied)
            return match.group(0) if match else ""
        except Exception:
            LOGGER.debug("Could not read copied Meet details", exc_info=True)
            return ""

    def _finish_invitation_dialog(self, window) -> None:
        for label in ("invite external guests", "send"):
            control = self._find_control(window, label, exact=True)
            if control is not None:
                try:
                    control.click_input()
                    self.sleep(0.6)
                except Exception:
                    LOGGER.debug("Could not click Calendar dialog", exc_info=True)

    def _find_control(self, window, text: str, *, exact: bool = False):
        needle = text.casefold()
        for control in self._controls(window):
            name = self._control_name(control).casefold().strip()
            if (exact and name == needle) or (not exact and needle in name):
                return control
        return None

    @staticmethod
    def _controls(window) -> list[Any]:
        try:
            return list(window.descendants())
        except Exception:
            return []

    @staticmethod
    def _control_name(control) -> str:
        try:
            return str(control.window_text() or "")
        except Exception:
            return ""
