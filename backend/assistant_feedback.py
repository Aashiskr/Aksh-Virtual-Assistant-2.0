from __future__ import annotations

from .assistant_status import idle_status
from .notifications import show_notification


class AssistantFeedbackMixin:
    """Routes user-visible feedback and enforces meeting silence."""

    def _on_reminder(self, item: dict) -> None:
        kind = item.get("kind", "reminder")
        message = item.get("message", "Reminder")
        spoken = f"{kind.title()}: {message}"
        if self._meeting_mode:
            return
        show_notification(spoken)
        self._say(spoken)
        self._return_to_idle()

    def _on_system_alert(self, message: str) -> None:
        if self._meeting_mode:
            return
        show_notification(message)
        self._say(message)
        self._return_to_idle()

    def _say(self, text: str) -> None:
        if self._meeting_mode:
            return
        self.message_callback("aksh", text)
        self.speaker.speak(text)

    def _status(self, state: str, text: str) -> None:
        if self._meeting_mode:
            return
        self.status_callback(state, text)

    def _return_to_idle(self) -> None:
        if self._closing.is_set():
            return
        self._show_idle_status()

    def _show_idle_status(self) -> None:
        if self._meeting_mode:
            self.status_callback(
                "working", "Meeting Mode · listening silently"
            )
            return
        state, text = idle_status(
            self.settings,
            friends=self.security.friends_mode,
            enrolled=self.voiceprint.enrolled,
            brain=self.brain.enabled,
            continuous_session_armed=self.voice.continuous_session_armed,
        )
        self._status(state, text)
