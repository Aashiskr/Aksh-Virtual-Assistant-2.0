from __future__ import annotations

import subprocess
import webbrowser

from .whatsapp_controls import find_edit
from .whatsapp_target import control_name, find_phone_target_editor


MESSAGE_LABELS = ("Type a message", "Message")


class WhatsAppPhoneChatMixin:
    """Opens a phone-number chat without accepting the previously open chat."""

    def _open_phone_chat(self, phone_number: str, platform: str):
        normalized_platform = self._platform(platform)
        if normalized_platform == "web":
            finder = self._find_web_window
        else:
            finder = self._find_desktop_window
        previous_window = finder()
        previous_editor = (
            find_edit(previous_window, MESSAGE_LABELS)
            if previous_window is not None
            else None
        )
        previous_name = control_name(previous_editor)

        if normalized_platform == "web":
            webbrowser.open(
                f"https://web.whatsapp.com/send?phone={phone_number}"
            )
        else:
            subprocess.Popen(
                [
                    "explorer.exe",
                    f"whatsapp://send?phone={phone_number}",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        window = self._wait_for(finder, timeout=30)
        if window is None:
            raise RuntimeError(
                "Number ka WhatsApp chat open nahi hua. Country code ke "
                "saath number dobara boliye."
            )
        self._focus(window)
        editor = self._wait_for(
            lambda: find_phone_target_editor(
                window,
                MESSAGE_LABELS,
                phone_number,
                previous_name,
            ),
            timeout=15,
        )
        if editor is None:
            raise RuntimeError(
                f"{phone_number} ki verified WhatsApp chat open nahi hui."
            )
        return window
