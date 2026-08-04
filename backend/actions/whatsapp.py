from __future__ import annotations

import time

import win32con
import win32gui

from .whatsapp_contact_finder import find_contact_control
from .whatsapp_calls import END_CALL_LABELS, WhatsAppCallMixin  # noqa: F401
from .whatsapp_controls import find_button, find_edit
from .whatsapp_keyboard import press_enter, replace_focused_text
from .whatsapp_names import base_contact_name
from .whatsapp_phone_chat import WhatsAppPhoneChatMixin
from .whatsapp_phone import normalize_whatsapp_number
from .whatsapp_search import contact_search_queries
from .whatsapp_target import control_name, find_target_editor
from .whatsapp_windows import WhatsAppWindowMixin


SEARCH_LABELS = ("Search or start a new chat", "Search")
MESSAGE_LABELS = ("Type a message", "Message")
CALL_LABELS = (
    "Voice call",
    "Audio call",
    "Start voice call",
    "Start an audio call",
)


class WhatsAppController(
    WhatsAppCallMixin,
    WhatsAppPhoneChatMixin,
    WhatsAppWindowMixin,
):
    """Controls WhatsApp through accessible UI elements, never fixed coordinates."""

    def __init__(self, default_country_code: str = "91"):
        digits = "".join(
            character
            for character in default_country_code
            if character.isdigit()
        )
        self.default_country_code = digits or "91"
        self._active_call_platform: str | None = None

    def send_message(self, contact: str, message: str, platform: str) -> None:
        self._with_com(lambda: self._send_message(contact, message, platform))

    def start_call(self, contact: str, platform: str) -> None:
        self._with_com(lambda: self._start_call(contact, platform))

    def probe(self, platform: str) -> dict[str, object]:
        result: dict[str, object] = {}

        def inspect() -> None:
            window, reused = self._get_window(platform)
            result.update(
                reused=reused,
                title=window.window_text(),
                search_available=bool(self._get_search_edit(window)),
            )

        self._with_com(inspect)
        return result

    def _send_message(self, contact: str, message: str, platform: str) -> None:
        window, _ = self._get_window(platform)
        editor = self._open_contact(window, contact)
        self._replace_text(window, editor, message)
        press_enter()

    def _start_call(self, contact: str, platform: str) -> None:
        window, _ = self._get_window(platform)
        phone_number = normalize_whatsapp_number(
            contact,
            default_country_code=self.default_country_code,
        )
        if phone_number:
            editor = self._open_contact(
                window,
                contact,
                prefer_first=True,
                allow_missing=True,
                match_timeout=4,
            )
            if editor is None:
                window = self._open_phone_chat(phone_number, platform)
        else:
            self._open_contact(
                window,
                contact,
                prefer_first=True,
                match_timeout=2.5,
            )
        button = self._wait_for_button(window, CALL_LABELS, timeout=8)
        self._click(button)
        self._active_call_platform = self._platform(platform)

    def _open_contact(
        self,
        window,
        contact: str,
        *,
        prefer_first: bool = False,
        allow_missing: bool = False,
        match_timeout: float = 8,
    ):
        search = self._get_search_edit(window)
        if search is None:
            raise RuntimeError(
                "WhatsApp window open hai, par chat search ready nahi hua. "
                "App ko ek baar foreground mein kholkar phir try karein."
            )
        queries = (
            contact_search_queries(contact)
            if prefer_first
            else [base_contact_name(contact) or contact]
        )
        match = None
        for query in queries:
            self._replace_text(window, search, query)
            match = self._wait_for(
                lambda query=query: find_contact_control(
                    window,
                    query,
                    search,
                    prefer_first=prefer_first,
                ),
                timeout=match_timeout,
            )
            if match is not None:
                break
        if match is None:
            self._replace_text(window, search, "")
            if allow_missing:
                return None
            attempted = ", ".join(queries[:4])
            raise RuntimeError(
                f"Contact '{contact}' ka WhatsApp result nahi mila. "
                f"Maine {attempted} spellings try ki."
            )
        selected_name = control_name(match)
        self._click(match)
        editor = self._wait_for(
            lambda: find_target_editor(
                window,
                MESSAGE_LABELS,
                contact,
                selected_name,
            ),
            timeout=2,
        )
        if editor is None:
            self._focus(window)
            try:
                match.click_input()
            except Exception:
                self._click(match)
            editor = self._wait_for(
                lambda: find_target_editor(
                    window,
                    MESSAGE_LABELS,
                    contact,
                    selected_name,
                ),
                timeout=8,
            )
        if not editor:
            raise RuntimeError(
                f"{contact} ki verified WhatsApp chat open nahi hui."
            )
        return editor

    def _get_search_edit(self, window):
        search = self._wait_for(
            lambda: find_edit(window, SEARCH_LABELS, prefer_top=True),
            timeout=6,
        )
        if search:
            return search
        window.maximize()
        self._focus(window)
        return self._wait_for(
            lambda: find_edit(window, SEARCH_LABELS, prefer_top=True),
            timeout=20,
        )

    def _wait_for_edit(self, window, labels, timeout: float):
        return self._wait_for(lambda: find_edit(window, labels), timeout)

    def _wait_for_button(self, window, labels, timeout: float):
        button = self._wait_for(lambda: find_button(window, labels), timeout)
        if button is None:
            raise RuntimeError("WhatsApp voice-call button nahi mila.")
        return button

    @staticmethod
    def _replace_text(window, control, value: str) -> None:
        WhatsAppController._focus(window)
        try:
            control.click_input()
        except Exception:
            control.set_focus()
        time.sleep(0.15)
        if not WhatsAppController._is_foreground(window):
            WhatsAppController._focus(window)
            control.set_focus()
        if not WhatsAppController._is_foreground(window):
            raise RuntimeError(
                "WhatsApp foreground mein nahi aa saka; dobara try karein."
            )
        replace_focused_text(value)

    @staticmethod
    def _click(control) -> None:
        try:
            control.invoke()
        except Exception:
            control.click_input()

    @staticmethod
    def _focus(window) -> None:
        try:
            handle = window.handle
            if win32gui.IsIconic(handle):
                win32gui.ShowWindow(handle, win32con.SW_RESTORE)
        except Exception:
            pass
        try:
            window.set_focus()
        except Exception:
            pass
        try:
            win32gui.SetForegroundWindow(window.handle)
        except Exception:
            pass
        time.sleep(0.6)

    @staticmethod
    def _is_foreground(window) -> bool:
        try:
            foreground = win32gui.GetForegroundWindow()
            return win32gui.GetAncestor(
                foreground, win32con.GA_ROOT
            ) == window.handle
        except Exception:
            return False

    @staticmethod
    def _wait_for(function, timeout: float):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                value = function()
                if value:
                    return value
            except Exception:
                pass
            time.sleep(0.25)
        return None

    @staticmethod
    def _platform(value: str) -> str:
        normalized = (value or "desktop").strip().casefold()
        return "web" if normalized in {"web", "whatsapp_web"} else "desktop"

    @staticmethod
    def _with_com(operation) -> None:
        import pythoncom

        pythoncom.CoInitialize()
        try:
            operation()
        finally:
            pythoncom.CoUninitialize()
