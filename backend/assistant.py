from __future__ import annotations

import logging
import threading
from typing import Callable

import speech_recognition as sr

from .actions import ActionRegistry
from .assistant_feedback import AssistantFeedbackMixin
from .config import AkshSettings
from .enrollment import OwnerEnrollment
from .brain import GroqBrain
from .command_processor import CommandProcessor
from .command_runtime import CommandRuntime
from .confirmations import ConfirmationManager
from .models import VoiceCapture
from .meeting.assistant_mode import MeetingModeMixin
from .monitors import BatteryMonitor, SmartEnvironmentMonitor
from .permissions import FriendModeController
from .remote import RemoteCommandRunner
from .security import SecurityManager
from .voice_session import VoiceCommandSession
from .audio import Speaker, VoicePrintManager, VoiceService, is_mic_off_command, match_wake


LOGGER = logging.getLogger(__name__)
StatusCallback = Callable[[str, str], None]
MessageCallback = Callable[[str, str], None]
MeetingCallback = Callable[[str, dict], None]


class AkshAssistant(MeetingModeMixin, AssistantFeedbackMixin):
    def __init__(
        self,
        settings: AkshSettings,
        *,
        status_callback: StatusCallback | None = None,
        message_callback: MessageCallback | None = None,
        meeting_callback: MeetingCallback | None = None,
    ):
        self.settings = settings
        self.status_callback = status_callback or (lambda state, text: None)
        self.message_callback = message_callback or (lambda role, text: None)
        self.meeting_callback = meeting_callback or (
            lambda event, payload: None
        )
        self.speaker = Speaker(
            rate=settings.tts_rate,
            neural_voice=settings.tts_voice,
            neural_rate=settings.tts_neural_rate,
            neural_pitch=settings.tts_pitch,
            neural_volume=settings.tts_volume,
        )
        self.voiceprint = VoicePrintManager(
            settings.data_dir / "owner_voiceprint.dat",
            threshold=settings.voice_match_threshold,
        )
        self.voice = VoiceService(settings, self.voiceprint)
        self.security = SecurityManager(
            confirm_sensitive_actions=settings.confirm_sensitive_actions
        )
        self.brain = GroqBrain(settings)
        self._setup_meeting_mode(settings)
        self.actions = ActionRegistry(settings, on_reminder=self._on_reminder)
        self.battery_monitor = BatteryMonitor(
            self._on_system_alert,
            state_path=settings.data_dir / "battery_monitor.json",
            full_warning_limit=settings.full_charge_warning_limit,
            full_warning_cooldown_seconds=(
                settings.full_charge_warning_cooldown_minutes * 60
            ),
        )
        self.environment_monitor = SmartEnvironmentMonitor()
        self.enrollment = OwnerEnrollment(
            self.voice,
            self.voiceprint,
            self.speaker,
            self._status,
            self._say,
        )
        self.confirmations = ConfirmationManager(
            settings,
            self.security,
            self._status,
            self.message_callback,
        )
        self.friend_mode = FriendModeController(
            self.security, self._status, self._say
        )
        self.processor = CommandProcessor(
            brain=self.brain,
            actions=self.actions,
            security=self.security,
            confirmations=self.confirmations,
            friend_mode=self.friend_mode,
            set_mic=self.set_wake_listener_enabled,
            status=self._status,
            say=self._say,
            message=self.message_callback,
            stop_speaking=self.speaker.stop_current,
        )
        self._active_lock = threading.Lock()
        self._closing = threading.Event()
        self.command_runtime = CommandRuntime(
            self.voice,
            self.speaker,
            self._status,
            self._say,
            self._active_lock.release,
            self._return_to_idle,
        )
        self.voice_session = VoiceCommandSession(
            settings,
            self.voice,
            self.voiceprint,
            self.speaker,
            self._status,
            self._say,
            self._handle_voice_capture,
        )
        self.remote_runner = RemoteCommandRunner(
            closing=self._closing,
            active_lock=self._active_lock,
            runtime=self.command_runtime,
            process=self.process_text,
            message=self.message_callback,
        )

    @property
    def friends_mode(self) -> bool:
        return self.security.friends_mode

    def start(self) -> None:
        self.actions.start()
        self.battery_monitor.start()
        if self.settings.smart_environment_enabled:
            self.environment_monitor.start()
        self.voice.start_wake_listener(
            callback=self._on_wake_phrase,
            friends_mode=lambda: self.security.friends_mode,
            status_callback=self._status,
        )
        self._show_idle_status()

    def activate(self, source: str = "pet") -> None:
        if self._closing.is_set():
            return
        if self._meeting_mode:
            self._status("working", "Meeting Mode active · silent coaching")
            return
        if not self.settings.wake_listener_enabled:
            self.set_wake_listener_enabled(True)
        if not self._active_lock.acquire(blocking=False):
            self._status("busy", "Already listening or working")
            return
        threading.Thread(
            target=self.command_runtime.run,
            args=(lambda: self.voice_session.run(source), source),
            name=f"aksh-activation-{source}",
            daemon=True,
        ).start()

    def greet(self) -> None:
        if not self._closing.is_set():
            self._say("नमस्ते")

    def process_typed(self, text: str) -> None:
        if not text.strip() or self._closing.is_set():
            return
        if self._meeting_mode:
            self._status("working", "Meeting Mode active · commands paused")
            return
        if not self._active_lock.acquire(blocking=False):
            self._status("busy", "Please wait")
            return

        def operation() -> None:
            self.process_text(text, is_owner=True, source="typed")

        threading.Thread(
            target=self.command_runtime.run,
            args=(operation, "typed"),
            name="aksh-typed",
            daemon=True,
        ).start()

    def run_remote_command(self, text: str) -> str:
        if self._meeting_mode:
            return "Meeting Mode active hai; normal commands paused hain."
        return self.remote_runner.run(text)

    def enroll_owner_voice(self) -> None:
        if not self._active_lock.acquire(blocking=False):
            self._status("busy", "Please wait")
            return
        threading.Thread(
            target=self._enrollment_worker,
            name="aksh-enrollment",
            daemon=True,
        ).start()

    def set_wake_listener_enabled(self, enabled: bool) -> None:
        self.settings.wake_listener_enabled = enabled
        self._status(
            "idle" if enabled else "sleeping",
            "Always listening on"
            if enabled and self.settings.continuous_listening_enabled
            else ("Wake listening on" if enabled else "Microphone listening off"),
        )

    def set_continuous_listening_enabled(self, enabled: bool) -> None:
        self.settings.continuous_listening_enabled = enabled
        text = "Always listening on" if enabled else "Wake phrase mode on"
        self._status("idle", text)

    def close(self) -> None:
        self._closing.set()
        self.meeting.close()
        self.voice.close()
        self.actions.close()
        self.battery_monitor.close()
        self.environment_monitor.close()
        self.speaker.close()

    def _handle_voice_capture(self, capture: VoiceCapture, source: str) -> None:
        self.message_callback("you", capture.text)
        if not self.security.speaker_is_allowed(capture.is_owner):
            score = f"{capture.verification_score:.2f}"
            LOGGER.info("Voice rejected with score %s", score)
            self._status("locked", "Voice not recognized")
            self._say("Sorry, aapki voice owner profile se match nahi hui.")
            return
        self.process_text(capture.text, is_owner=capture.is_owner, source=source)

    def process_text(self, text: str, *, is_owner: bool, source: str) -> str:
        return self.processor.process(
            text, is_owner=is_owner, source=source
        )

    def _enrollment_worker(self) -> None:
        try:
            self.enrollment.run()
        finally:
            self._active_lock.release()
            self._return_to_idle()

    def _on_wake_phrase(
        self, text: str, audio: sr.AudioData, is_owner: bool, score: float
    ) -> None:
        LOGGER.info(
            "Wake phrase accepted: owner=%s score=%.3f friends=%s",
            is_owner,
            score,
            self.security.friends_mode,
        )
        command = self._command_after_wake(text)
        if is_mic_off_command(command or text):
            self.set_wake_listener_enabled(False)
            self._say("Theek hai, microphone listening off kar di.")
            return
        if not command:
            self.activate("wake")
            return
        if not self._active_lock.acquire(blocking=False):
            self._status("busy", "Already listening or working")
            return

        def operation() -> None:
            self.message_callback("you", command)
            self.process_text(command, is_owner=is_owner, source="wake-inline")
        threading.Thread(
            target=self.command_runtime.run,
            args=(operation, "wake-inline"),
            name="aksh-inline-wake-command",
            daemon=True,
        ).start()

    def _command_after_wake(self, text: str) -> str:
        wake_found, command = match_wake(text, self.settings.wake_phrases)
        if not wake_found and self.settings.continuous_listening_enabled:
            return text.strip()
        return command
