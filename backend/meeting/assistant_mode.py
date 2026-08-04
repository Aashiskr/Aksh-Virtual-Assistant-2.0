from __future__ import annotations

from ..config import AkshSettings
from .controller import MeetingController


class MeetingModeMixin:
    """Meeting lifecycle kept separate from normal assistant commands."""

    def _setup_meeting_mode(self, settings: AkshSettings) -> None:
        self._meeting_mode = False
        self.meeting = MeetingController(settings, self._on_meeting_event)

    @property
    def meeting_active(self) -> bool:
        return self._meeting_mode

    def start_meeting_mode(self) -> None:
        if self._closing.is_set() or self._meeting_mode:
            return
        if self._active_lock.locked():
            raise RuntimeError("Current command finish hone ke baad try karein.")
        self.speaker.set_muted(True)
        self.voice.pause_wake_listener()
        self._meeting_mode = True
        try:
            self.meeting.start()
        except Exception:
            self._meeting_mode = False
            self.speaker.set_muted(False)
            self.voice.resume_wake_listener()
            raise
        self.status_callback(
            "working", "Meeting Mode · listening silently"
        )

    def stop_meeting_mode(self) -> None:
        if not self._meeting_mode:
            return
        self.status_callback("working", "Finishing meeting report…")
        self.meeting.stop_async()

    def _on_meeting_event(self, event: str, payload: dict) -> None:
        if event == "finished":
            self._meeting_mode = False
            self.speaker.set_muted(False)
            self.voice.resume_wake_listener()
            self._show_idle_status()
        self.meeting_callback(event, payload)
