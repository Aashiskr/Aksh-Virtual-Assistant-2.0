from __future__ import annotations

import logging
import threading
import time
from typing import Callable

import speech_recognition as sr

from ..config import AkshSettings
from ..integrations.groq_speech import GroqSpeechTranscriber
from ..models import VoiceCapture
from .clap import DoubleClapDetector
from .control import is_mic_off_command
from .replay_guard import VoiceReplayGuard
from .voiceprint import VoicePrintManager
from .wake import match_wake


LOGGER = logging.getLogger(__name__)


class VoiceInputCancelled(Exception):
    """Raised when a microphone capture is invalidated while it is in flight."""


class VoiceService:
    def __init__(self, settings: AkshSettings, voiceprint: VoicePrintManager):
        self.settings = settings
        self.voiceprint = voiceprint
        self.groq_transcriber = GroqSpeechTranscriber(settings)
        self.double_clap_detector = DoubleClapDetector()
        self.replay_guard = VoiceReplayGuard(
            settings.data_dir / "voice_replay_guard.json"
        )
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 300
        self.recognizer.pause_threshold = 0.8
        self._calibrated = False
        self._microphone_lock = threading.Lock()
        self._pause_lock = threading.Lock()
        self._pause_depth = 0
        self._pause_wake = threading.Event()
        self._stop = threading.Event()
        self._wake_thread: threading.Thread | None = None
        self._input_state_lock = threading.RLock()
        self._input_generation = 0
        self._active_source: sr.Microphone | None = None

    def start_wake_listener(
        self,
        callback: Callable[[str, sr.AudioData, bool, float], None],
        friends_mode: Callable[[], bool],
        status_callback: Callable[[str, str], None] | None = None,
        double_clap_callback: Callable[[], None] | None = None,
    ) -> None:
        if self._wake_thread and self._wake_thread.is_alive():
            return

        def run() -> None:
            while not self._stop.is_set():
                voice_enabled = self.settings.wake_listener_enabled
                clap_enabled = (
                    self.settings.double_clap_enabled
                    and double_clap_callback is not None
                )
                if self._pause_wake.is_set() or not (
                    voice_enabled or clap_enabled
                ):
                    time.sleep(0.15)
                    continue
                if (
                    voice_enabled
                    and not clap_enabled
                    and self.settings.voice_lock_enabled
                    and not self.voiceprint.enrolled
                ):
                    time.sleep(0.5)
                    continue
                try:
                    if not voice_enabled and clap_enabled:
                        if self._capture_double_clap():
                            if (
                                not self.settings.double_clap_enabled
                                or self.settings.wake_listener_enabled
                                or self._pause_wake.is_set()
                                or self._stop.is_set()
                            ):
                                continue
                            LOGGER.info(
                                "Double clap detected; opening command microphone"
                            )
                            double_clap_callback()
                        continue
                    generation = self._current_input_generation()
                    audio = self.capture_audio(timeout=1.2, phrase_time_limit=4.5)
                    if audio is None:
                        continue
                    if not self._background_input_is_current(generation):
                        continue
                    if (
                        double_clap_callback is not None
                        and self.settings.double_clap_enabled
                        and self.double_clap_detector.detected(audio)
                    ):
                        LOGGER.info("Double clap detected; opening command microphone")
                        double_clap_callback()
                        continue
                    if not self.settings.wake_listener_enabled:
                        continue
                    if (
                        self.settings.voice_lock_enabled
                        and not self.voiceprint.enrolled
                    ):
                        continue
                    text = self.recognize(audio)
                    if not self._background_input_is_current(generation):
                        continue
                    wake_found, command = match_wake(
                        text, self.settings.wake_phrases
                    )
                    if (
                        not wake_found
                        and not self.settings.continuous_listening_enabled
                    ):
                        continue
                    accepted, reason = self._accept_background_trigger(
                        text,
                        wake_found=wake_found,
                        command=command,
                    )
                    if not accepted:
                        LOGGER.info("Voice trigger ignored: reason=%s", reason)
                        continue
                    if not self._background_input_is_current(generation):
                        continue
                    if self.settings.voice_lock_enabled:
                        is_owner, score = self.voiceprint.verify(audio)
                    else:
                        is_owner, score = True, 1.0
                    if not self._background_input_is_current(generation):
                        continue
                    LOGGER.info(
                        "Voice trigger heard: mode=%s owner=%s score=%.3f friends=%s",
                        "wake" if wake_found else "continuous",
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

    def _current_input_generation(self) -> int:
        with self._input_state_lock:
            return self._input_generation

    def _input_is_current(self, generation: int) -> bool:
        with self._input_state_lock:
            return generation == self._input_generation and not self._stop.is_set()

    def _background_input_is_current(self, generation: int) -> bool:
        return (
            self._input_is_current(generation)
            and self.settings.wake_listener_enabled
            and not self._pause_wake.is_set()
        )

    def cancel_pending_input(self) -> None:
        """Invalidate queued audio and interrupt the microphone stream if possible."""

        with self._input_state_lock:
            self._input_generation += 1
            active_source = self._active_source
        self.disarm_continuous_session()
        if active_source is None or active_source.stream is None:
            return
        try:
            active_source.stream.pyaudio_stream.stop_stream()
        except Exception as exc:
            LOGGER.debug("Active microphone stop: %s", exc)

    def _capture_double_clap(self) -> bool:
        if not self._microphone_lock.acquire(timeout=1.0):
            return False
        try:
            with sr.Microphone(
                device_index=self.settings.microphone_device_index
            ) as source:
                self.double_clap_detector.reset_stream()
                LOGGER.info(
                    "Double-clap sensor ready: device=%s rate=%s",
                    self.settings.microphone_device_index,
                    source.SAMPLE_RATE,
                )
                while (
                    self.settings.double_clap_enabled
                    and not self.settings.wake_listener_enabled
                    and not self._pause_wake.is_set()
                    and not self._stop.is_set()
                ):
                    raw = source.stream.read(source.CHUNK)
                    audio = sr.AudioData(
                        raw,
                        source.SAMPLE_RATE,
                        source.SAMPLE_WIDTH,
                    )
                    if self.double_clap_detector.detected_chunk(audio):
                        return True
        finally:
            self._microphone_lock.release()
        return False

    def pause_wake_listener(self) -> None:
        with self._pause_lock:
            self._pause_depth += 1
            self._pause_wake.set()

    def resume_wake_listener(self) -> None:
        with self._pause_lock:
            self._pause_depth = max(0, self._pause_depth - 1)
            if self._pause_depth == 0:
                self._pause_wake.clear()

    @property
    def continuous_session_armed(self) -> bool:
        return self.replay_guard.continuous_session_armed

    def arm_continuous_session(self) -> None:
        self.replay_guard.arm_continuous_session()

    def disarm_continuous_session(self) -> None:
        self.replay_guard.disarm_continuous_session()

    def listen_for_command(self) -> VoiceCapture:
        generation = self._current_input_generation()
        self.pause_wake_listener()
        try:
            try:
                audio = self.capture_audio(
                    timeout=self.settings.listen_timeout_seconds,
                    phrase_time_limit=self.settings.phrase_time_limit_seconds,
                )
            except Exception:
                if not self._input_is_current(generation):
                    raise VoiceInputCancelled() from None
                raise
            if not self._input_is_current(generation):
                raise VoiceInputCancelled()
            if audio is None:
                raise sr.WaitTimeoutError()
            text = self.recognize(audio)
            if not self._input_is_current(generation):
                raise VoiceInputCancelled()
            LOGGER.info("Command recognized: %s", text)
            if self.settings.voice_lock_enabled:
                is_owner, score = self.voiceprint.verify(audio)
            else:
                is_owner, score = True, 1.0
            if not self._input_is_current(generation):
                raise VoiceInputCancelled()
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
                with self._input_state_lock:
                    self._active_source = source
                try:
                    if not self._calibrated:
                        self.recognizer.adjust_for_ambient_noise(
                            source, duration=0.8
                        )
                        self.recognizer.energy_threshold = max(
                            150, self.recognizer.energy_threshold
                        )
                        self._calibrated = True
                    return self.recognizer.listen(
                        source,
                        timeout=timeout,
                        phrase_time_limit=phrase_time_limit,
                    )
                finally:
                    with self._input_state_lock:
                        if self._active_source is source:
                            self._active_source = None
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

    def _accept_background_trigger(
        self,
        text: str,
        *,
        wake_found: bool,
        command: str,
    ) -> tuple[bool, str]:
        if is_mic_off_command(command or text):
            return True, "mic_off"
        if wake_found and not command.strip():
            self.replay_guard.arm_continuous_session()
            return True, "wake_only"
        candidate = command if wake_found else text
        return self.replay_guard.allow(candidate, explicit_wake=wake_found)

    def close(self) -> None:
        self._stop.set()
        self._pause_wake.set()
        self.cancel_pending_input()
