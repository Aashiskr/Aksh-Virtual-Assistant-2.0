from __future__ import annotations

import logging
from collections.abc import Callable

import speech_recognition as sr

from .audio import Speaker, VoicePrintManager, VoiceService
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
        handle: Callable[[VoiceCapture, str], None],
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
        try:
            capture = self.voice.listen_for_command()
        except sr.WaitTimeoutError:
            self.say("Mujhe koi command nahi sunai di.")
            return
        except sr.UnknownValueError:
            self.say("Main samajh nahi paaya. Please dobara try kijiye.")
            return
        except Exception as exc:
            LOGGER.warning("Command listening failed: %s", exc)
            self.say("Microphone ya speech recognition mein problem aayi.")
            return
        self.handle(capture, source)
