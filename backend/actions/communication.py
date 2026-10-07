from __future__ import annotations

from typing import Any

from ..calendar_meetings import GoogleMeetingScheduler, MeetingStore
from ..models import ActionResult
from .base import ActionGroup
from .whatsapp import WhatsAppController


class CommunicationActions(ActionGroup):
    def __init__(self, settings):
        super().__init__(settings)
        self.whatsapp = WhatsAppController(settings.whatsapp_country_code)
        self._meeting_scheduler: GoogleMeetingScheduler | None = None

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
        self.required(parameters, "time")
        if self._meeting_scheduler is None:
            self._meeting_scheduler = GoogleMeetingScheduler(self.settings)
        meeting = self._meeting_scheduler.schedule(parameters)
        account = meeting.get("account_email") or meeting["account"]
        return ActionResult(
            True,
            f"Meeting {meeting['time']} ke liye {account} account se "
            "schedule ho gayi. Meet link phone app mein copy kar sakte hain.",
            data={"meeting": meeting},
        )

    def send_meeting(self, parameters: dict[str, Any]) -> ActionResult:
        contact = self.required(parameters, "contact")
        when = self.required(parameters, "time").lower()
        store = MeetingStore(self.settings.data_dir / "meetings.json")
        meetings = store.all()
        if not meetings:
            return ActionResult(False, "Koi saved meeting nahi mili.")
        match = next(
            (
                item
                for item in reversed(meetings)
                if when in str(item.get("time", "")).lower()
            ),
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
