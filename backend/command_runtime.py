from __future__ import annotations

import logging
from collections.abc import Callable

from .audio import Speaker, VoiceService


LOGGER = logging.getLogger(__name__)


class CommandRuntime:
    """Keeps wake listening paused while one command and its reply complete."""

    def __init__(
        self,
        voice: VoiceService,
        speaker: Speaker,
        status: Callable[[str, str], None],
        say: Callable[[str], None],
        release: Callable[[], None],
        on_idle: Callable[[], None],
    ):
        self.voice = voice
        self.speaker = speaker
        self.status = status
        self.say = say
        self.release = release
        self.on_idle = on_idle

    def run(self, operation: Callable[[], None], source: str) -> None:
        self.voice.pause_wake_listener()
        try:
            operation()
        except Exception:
            LOGGER.exception("Command worker failed: source=%s", source)
            self.status("error", "Command failed · listening will continue")
            self.say("Command complete nahi hua, lekin main ab bhi sun raha hoon.")
        finally:
            self.speaker.wait_until_idle(timeout=30.0)
            self.voice.resume_wake_listener()
            self.release()
            LOGGER.info("Command finished; listener re-armed: source=%s", source)
            self.on_idle()
