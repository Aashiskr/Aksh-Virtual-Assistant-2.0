from __future__ import annotations

import subprocess
import webbrowser

import psutil
import win32gui
import win32process


BROWSER_PROCESSES = {"brave.exe", "chrome.exe", "firefox.exe", "msedge.exe"}
WHATSAPP_APP_ID = "5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"


class WhatsAppWindowMixin:
    """Finds, launches, and reuses WhatsApp desktop or browser windows."""

    def _get_window(self, platform: str):
        normalized = self._platform(platform)
        window = (
            self._find_desktop_window()
            if normalized == "desktop"
            else self._find_web_window()
        )
        reused = window is not None
        if window is None:
            self._launch(normalized)
            finder = (
                self._find_desktop_window
                if normalized == "desktop"
                else self._find_web_window
            )
            window = self._wait_for(finder, timeout=30)
        if window is None:
            raise RuntimeError(f"WhatsApp {normalized} window nahi mili.")
        self._focus(window)
        return window, reused

    def _find_desktop_window(self):
        return self._window_matching(
            lambda process, title: process.startswith("whatsapp")
            and "whatsapp" in title
        )

    def _find_web_window(self):
        active = self._window_matching(
            lambda process, title: process in BROWSER_PROCESSES
            and "whatsapp" in title
        )
        if active:
            return active
        for handle, process, _ in self._top_windows():
            if process not in BROWSER_PROCESSES:
                continue
            window = self._wrap(handle)
            try:
                tabs = window.descendants(control_type="TabItem")
            except Exception:
                continue
            for tab in tabs:
                if "whatsapp" in (tab.element_info.name or "").casefold():
                    self._click(tab)
                    self._focus(window)
                    return window
        return None

    def _window_matching(self, predicate):
        for handle, process, title in self._top_windows():
            if predicate(process, title):
                return self._wrap(handle)
        return None

    @staticmethod
    def _top_windows() -> list[tuple[int, str, str]]:
        rows: list[tuple[int, str, str]] = []

        def collect(handle, _):
            if not win32gui.IsWindowVisible(handle):
                return
            title = win32gui.GetWindowText(handle).strip().casefold()
            if not title:
                return
            try:
                _, process_id = win32process.GetWindowThreadProcessId(handle)
                process = psutil.Process(process_id).name().casefold()
                rows.append((handle, process, title))
            except (psutil.Error, OSError):
                pass

        win32gui.EnumWindows(collect, None)
        return rows

    @staticmethod
    def _wrap(handle: int):
        from pywinauto import Desktop

        return Desktop(backend="uia").window(handle=handle)

    @staticmethod
    def _launch(platform: str) -> None:
        if platform == "web":
            webbrowser.open("https://web.whatsapp.com/")
            return
        subprocess.Popen(
            [
                "explorer.exe",
                f"shell:AppsFolder\\{WHATSAPP_APP_ID}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
