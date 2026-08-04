from __future__ import annotations

import logging
from typing import Callable

import speech_recognition as sr

from .audio import Speaker, VoicePrintManager, VoiceService


LOGGER = logging.getLogger(__name__)


class OwnerEnrollment:
    def __init__(
        self,
        voice: VoiceService,
        voiceprint: VoicePrintManager,
        speaker: Speaker,
        status: Callable[[str, str], None],
        say: Callable[[str], None],
    ):
        self.voice = voice
        self.voiceprint = voiceprint
        self.speaker = speaker
        self.status = status
        self.say = say

    def run(self) -> bool:
        samples: list[sr.AudioData] = []
        phrases = [
            "Hey Aksh, this is my voice.",
            "Aksh, please recognize me as the owner.",
            "My voice gives permission to Aksh.",
        ]
        self.voice.pause_wake_listener()
        try:
            self.status("enrolling", "Voice enrollment · quiet room recommended")
            self.speaker.speak(
                "Owner voice setup start kar rahe hain. Quiet room mein normal "
                "voice mein teen sentences boliye.",
                block=True,
            )
            for index, phrase in enumerate(phrases, start=1):
                self.status("enrolling", f"Sample {index}/3 · “{phrase}”")
                self.speaker.speak(f"Sample {index}. Please say: {phrase}", block=True)
                try:
                    audio = self.voice.capture_audio(
                        timeout=8.0, phrase_time_limit=9.0
                    )
                except sr.WaitTimeoutError:
                    audio = None
                if audio is None:
                    raise ValueError(f"Sample {index} record nahi hua.")
                samples.append(audio)
            self.voiceprint.enroll(samples)
            self.status("idle", "Owner voice enrolled · Say “Hey Aksh”")
            self.say("Owner voice successfully enrolled. Voice lock active hai.")
            return True
        except Exception as exc:
            LOGGER.warning("Voice enrollment failed: %s", exc)
            self.status("setup", "Enrollment failed · try again")
            self.say(f"Voice enrollment complete nahi hua. {exc}")
            return False
        finally:
            self.voice.resume_wake_listener()
