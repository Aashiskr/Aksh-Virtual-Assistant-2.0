from __future__ import annotations

from .whatsapp_controls import find_button
from .whatsapp_windows import BROWSER_PROCESSES


END_CALL_LABELS = (
    "End call",
    "End voice call",
    "End audio call",
    "End video call",
    "Hang up",
    "Hangup",
    "Cancel call",
    "Cancel voice call",
    "Cancel audio call",
    "Cancel video call",
    "Decline call",
    "Leave call",
)


class WhatsAppCallMixin:
    """Ends either a connected call or an unanswered outgoing call."""

    _active_call_platform: str | None

    def end_call(self, platform: str = "desktop") -> None:
        self._with_com(lambda: self._end_call(platform))

    def _end_call(self, platform: str) -> None:
        requested = self._platform(platform)
        preferred = self._active_call_platform or requested
        platforms = [preferred, "web" if preferred == "desktop" else "desktop"]
        windows: list[object] = []
        seen_handles: set[int] = set()

        def refresh_windows(*, discover_web_tab: bool = False) -> None:
            for candidate_platform in platforms:
                candidates = self._existing_windows_for_call(
                    candidate_platform,
                    discover_web_tab=discover_web_tab,
                )
                for window in candidates:
                    handle = getattr(window, "handle", id(window))
                    if handle not in seen_handles:
                        seen_handles.add(handle)
                        windows.append(window)

        refresh_windows(discover_web_tab=True)

        def find_control():
            refresh_windows()
            for window in windows:
                button = find_button(window, END_CALL_LABELS)
                if button is not None:
                    return window, button
            return None

        match = self._wait_for(find_control, timeout=8)
        if match is None:
            raise RuntimeError(
                "Koi active ya ringing WhatsApp call ka end button nahi mila."
            )
        window, button = match
        self._focus(window)
        self._click(button)

        if self._wait_for(
            lambda: self._call_control_gone(window),
            timeout=4,
        ) is None:
            current = find_button(window, END_CALL_LABELS)
            if current is not None:
                self._click(current)
            if self._wait_for(
                lambda: self._call_control_gone(window),
                timeout=3,
            ) is None:
                raise RuntimeError(
                    "WhatsApp call end button click hua, par call band "
                    "hone ki confirmation nahi mili."
                )
        self._active_call_platform = None

    def _existing_windows_for_call(
        self,
        platform: str,
        *,
        discover_web_tab: bool = False,
    ) -> list[object]:
        normalized = self._platform(platform)
        windows: list[object] = []
        if normalized == "desktop":
            for handle, process, _ in self._top_windows():
                if process.startswith("whatsapp"):
                    windows.append(self._wrap(handle))
            return windows

        for handle, process, title in self._top_windows():
            if process in BROWSER_PROCESSES and "whatsapp" in title:
                windows.append(self._wrap(handle))
        if discover_web_tab:
            web_window = self._find_web_window()
            if web_window is not None and all(
                item.handle != web_window.handle for item in windows
            ):
                windows.append(web_window)
        return windows

    @staticmethod
    def _call_control_gone(window) -> bool:
        try:
            return find_button(window, END_CALL_LABELS) is None
        except Exception:
            return True
