from __future__ import annotations

import json
import time
import webbrowser
from typing import Any

from ..models import ActionResult
from .base import ActionGroup
from .whatsapp import WhatsAppController


class CommunicationActions(ActionGroup):
    def __init__(self, settings):
        super().__init__(settings)
        self.whatsapp = WhatsAppController(settings.whatsapp_country_code)

    def whatsapp_message(self, parameters: dict[str, Any]) -> ActionResult:
        contact = self.required(parameters, "contact")
        message = self.required(parameters, "message")
        platform = str(parameters.get("platform") or "desktop")
        self.whatsapp.send_message(contact, message, platform)
        location = "WhatsApp Web" if platform.casefold() == "web" else "WhatsApp app"
        return ActionResult(True, f"{location} se {contact} ko message send kar diya.")

    def whatsapp_call(self, parameters: dict[str, Any]) -> ActionResult:
        contact = self.required(parameters, "contact")
        platform = str(parameters.get("platform") or "desktop")
        self.whatsapp.start_call(contact, platform)
        location = "WhatsApp Web" if platform.casefold() == "web" else "WhatsApp app"
        return ActionResult(True, f"{location} se {contact} ko call kar raha hoon.")

    def whatsapp_end_call(self, parameters: dict[str, Any]) -> ActionResult:
        platform = str(parameters.get("platform") or "desktop")
        self.whatsapp.end_call(platform)
        return ActionResult(True, "WhatsApp call cut kar di.")

    def schedule_meeting(self, parameters: dict[str, Any]) -> ActionResult:
        import pyautogui
        import pyperclip

        when = self.required(parameters, "time")
        webbrowser.open("https://meet.google.com/new")
        time.sleep(6)
        pyautogui.hotkey("alt", "d")
        pyautogui.hotkey("ctrl", "c")
        link = pyperclip.paste()
        if not str(link).startswith("http"):
            return ActionResult(False, "Meet open hua, link copy nahi ho paaya.")
        path = self.settings.data_dir / "meetings.json"
        meetings = []
        if path.exists():
            try:
                meetings = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                meetings = []
        meetings.append({"time": when, "link": str(link)})
        path.write_text(json.dumps(meetings, indent=2), encoding="utf-8")
        return ActionResult(True, f"Meeting {when} ke liye create aur save ho gayi.")

    def send_meeting(self, parameters: dict[str, Any]) -> ActionResult:
        contact = self.required(parameters, "contact")
        when = self.required(parameters, "time").lower()
        path = self.settings.data_dir / "meetings.json"
        if not path.exists():
            return ActionResult(False, "Koi saved meeting nahi mili.")
        meetings = json.loads(path.read_text(encoding="utf-8"))
        match = next(
            (item for item in reversed(meetings) if when in item["time"].lower()),
            None,
        )
        if not match:
            return ActionResult(False, f"{when} ki meeting nahi mili.")
        return self.whatsapp_message(
            {
                "contact": contact,
                "message": f"Meeting link for {match['time']}: {match['link']}",
            }
        )
