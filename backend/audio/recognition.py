from __future__ import annotations

import logging
import threading
import time
from typing import Callable

import speech_recognition as sr

from ..config import AkshSettings
from ..integrations.groq_speech import GroqSpeechTranscriber
from ..models import VoiceCapture
from .voiceprint import VoicePrintManager
from .wake import match_wake


LOGGER = logging.getLogger(__name__)


class VoiceService:
    def __init__(self, settings: AkshSettings, voiceprint: VoicePrintManager):
        self.settings = settings
        self.voiceprint = voiceprint
        self.groq_transcriber = GroqSpeechTranscriber(settings)
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 120
        self.recognizer.pause_threshold = 0.8
        self._calibrated = False
        self._microphone_lock = threading.Lock()
        self._pause_lock = threading.Lock()
        self._pause_depth = 0
        self._pause_wake = threading.Event()
        self._stop = threading.Event()
        self._wake_thread: threading.Thread | None = None

    def start_wake_listener(
        self,
        callback: Callable[[str, sr.AudioData, bool, float], None],
        friends_mode: Callable[[], bool],
        status_callback: Callable[[str, str], None] | None = None,
    ) -> None:
        if self._wake_thread and self._wake_thread.is_alive():
            return

        def run() -> None:
            while not self._stop.is_set():
                if self._pause_wake.is_set() or not self.settings.wake_listener_enabled:
                    time.sleep(0.15)
                    continue
                if self.settings.voice_lock_enabled and not self.voiceprint.enrolled:
                    time.sleep(0.5)
                    continue
                try:
                    audio = self.capture_audio(timeout=1.2, phrase_time_limit=4.5)
                    if audio is None:
                        continue
                    if self._pause_wake.is_set() or self._stop.is_set():
                        continue
                    text = self.recognize(audio)
                    if self._pause_wake.is_set() or self._stop.is_set():
                        continue
                    wake_found, _ = match_wake(text, self.settings.wake_phrases)
                    if not wake_found and not self.settings.continuous_listening_enabled:
                        continue
                    if self.settings.voice_lock_enabled:
                        is_owner, score = self.voiceprint.verify(audio)
                    else:
                        is_owner, score = True, 1.0
                    LOGGER.info(
                        "Wake phrase heard: owner=%s score=%.3f friends=%s",
                        is_owner,
                        score,
                        friends_mode(),
                    )
                    if friends_mode() or is_owner:
                        callback(text, audio, is_owner, score)
                    elif status_callback:
                        status_callback("locked", "Voice not recognized")
                except sr.WaitTimeoutError:
                    continue
                except Exception as exc:
                    LOGGER.debug("Wake listener: %s", exc)
                    time.sleep(0.5)

        self._wake_thread = threading.Thread(
            target=run, name="aksh-wake-listener", daemon=True
        )
        self._wake_thread.start()

    def pause_wake_listener(self) -> None:
        with self._pause_lock:
            self._pause_depth += 1
            self._pause_wake.set()

    def resume_wake_listener(self) -> None:
        with self._pause_lock:
            self._pause_depth = max(0, self._pause_depth - 1)
            if self._pause_depth == 0:
                self._pause_wake.clear()

    def listen_for_command(self) -> VoiceCapture:
        self.pause_wake_listener()
        try:
            audio = self.capture_audio(
                timeout=self.settings.listen_timeout_seconds,
                phrase_time_limit=self.settings.phrase_time_limit_seconds,
            )
            if audio is None:
                raise sr.WaitTimeoutError()
            text = self.recognize(audio)
            LOGGER.info("Command recognized: %s", text)
            if self.settings.voice_lock_enabled:
                is_owner, score = self.voiceprint.verify(audio)
            else:
                is_owner, score = True, 1.0
            return VoiceCapture(text, audio, is_owner, score)
        finally:
            self.resume_wake_listener()

    def capture_audio(
        self, *, timeout: float, phrase_time_limit: float
    ) -> sr.AudioData | None:
        if not self._microphone_lock.acquire(timeout=max(1.0, timeout + 1)):
            return None
        try:
            with sr.Microphone(
                device_index=self.settings.microphone_device_index
            ) as source:
                if not self._calibrated:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.6)
                    self.recognizer.energy_threshold = max(
                        50, min(250, self.recognizer.energy_threshold)
                    )
                    self._calibrated = True
                return self.recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_time_limit
                )
        finally:
            self._microphone_lock.release()

    def recognize(self, audio: sr.AudioData) -> str:
        errors: list[Exception] = []
        if self.groq_transcriber.enabled:
            try:
                return self.groq_transcriber.transcribe_audio(audio)
            except Exception as exc:
                LOGGER.warning(
                    "Groq speech recognition failed; trying Google: %s", exc
                )
                errors.append(exc)
        for language in (self.settings.language, "hi-IN"):
            try:
                text = self.recognizer.recognize_google(audio, language=language)
                if text:
                    return str(text).strip()
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise errors[-1]
        raise sr.UnknownValueError()

    def close(self) -> None:
        self._stop.set()
        self._pause_wake.set()
