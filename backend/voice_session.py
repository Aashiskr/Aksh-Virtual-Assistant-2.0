from __future__ import annotations

import logging
from collections.abc import Callable

import speech_recognition as sr

from .audio import (
    Speaker,
    VoiceInputCancelled,
    VoicePrintManager,
    VoiceService,
    mute_output_while_listening,
)
from .config import AkshSettings
from .models import VoiceCapture


LOGGER = logging.getLogger(__name__)


class VoiceCommandSession:
    """Runs the prompt, microphone capture, and recognition error handling."""

    def __init__(
        self,
        settings: AkshSettings,
        voice: VoiceService,
        voiceprint: VoicePrintManager,
        speaker: Speaker,
        status: Callable[[str, str], None],
        say: Callable[[str], None],
        handle: Callable[[VoiceCapture, str], bool],
    ):
        self.settings = settings
        self.voice = voice
        self.voiceprint = voiceprint
        self.speaker = speaker
        self.status = status
        self.say = say
        self.handle = handle

    def run(self, source: str) -> None:
        if self.settings.voice_lock_enabled and not self.voiceprint.enrolled:
            self.status("setup", "Owner voice setup required")
            self.say(
                "Pehle owner voice enroll kijiye. Pet par right-click karke "
                "Enroll owner voice choose karein."
            )
            return
        self.status("awake", "Ji, batayiye…")
        self.speaker.speak("जी, बताइए क्या करना है?", block=True)
        self.status("listening", "Listening · speak now")
        capture = self._listen(followup=False)
        if capture is None:
            return
        needs_followup = bool(self.handle(capture, source))
        limit = max(1, int(getattr(self.settings, "voice_followup_turn_limit", 3)))
        for _ in range(limit):
            if not needs_followup:
                return
            self.speaker.wait_until_idle(timeout=30.0)
            self.status("listening", "Listening for your answer…")
            capture = self._listen(followup=True)
            if capture is None:
                return
            needs_followup = bool(self.handle(capture, source))
        if needs_followup:
            self.say("Mujhe abhi bhi poori detail nahi mili; baad mein dobara try karein.")

    def _listen(self, *, followup: bool) -> VoiceCapture | None:
        try:
            with mute_output_while_listening(
                getattr(self.settings, "mute_output_while_listening", True)
            ):
                return self.voice.listen_for_command()
        except VoiceInputCancelled:
            LOGGER.info("Command microphone capture cancelled")
        except sr.WaitTimeoutError:
            message = (
                "Mujhe koi jawab nahi sunai diya."
                if followup
                else "Mujhe koi command nahi sunai di."
            )
            self.say(message)
        except sr.UnknownValueError:
            self.say("Main samajh nahi paaya. Please dobara try kijiye.")
        except Exception as exc:
            LOGGER.warning("Command listening failed: %s", exc)
            self.say("Microphone ya speech recognition mein problem aayi.")
        return None
