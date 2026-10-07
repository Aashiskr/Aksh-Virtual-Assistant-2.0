import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from backend.audio import (
    VoiceInputCancelled,
    VoicePrintManager,
    VoiceService,
    is_mic_off_command,
)
from backend.models import BrainResponse
from backend.command_processor import CommandProcessor
from backend.config import AkshSettings


class VoiceServiceStateTests(unittest.TestCase):
    def make_service(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        settings = AkshSettings(voice_lock_enabled=False)
        voiceprint = VoicePrintManager(Path(folder.name) / "voice.dat")
        return VoiceService(settings, voiceprint)

    def test_nested_pause_only_rearms_after_final_resume(self):
        service = self.make_service()
        service.pause_wake_listener()
        service.pause_wake_listener()
        service.resume_wake_listener()
        self.assertTrue(service._pause_wake.is_set())
        service.resume_wake_listener()
        self.assertFalse(service._pause_wake.is_set())

    def test_open_voice_mode_does_not_call_voiceprint(self):
        service = self.make_service()
        audio = object()
        service.capture_audio = Mock(return_value=audio)
        service.recognize = Mock(return_value="chrome kholo")
        service.voiceprint.verify = Mock(side_effect=AssertionError("must not run"))
        capture = service.listen_for_command()
        self.assertTrue(capture.is_owner)
        self.assertEqual(capture.verification_score, 1.0)

    def test_mic_off_invalidates_command_audio_already_being_captured(self):
        service = self.make_service()
        audio = object()

        def disable_during_capture(**_kwargs):
            service.cancel_pending_input()
            return audio

        service.capture_audio = Mock(side_effect=disable_during_capture)
        service.recognize = Mock(return_value="random background words")

        with self.assertRaises(VoiceInputCancelled):
            service.listen_for_command()

        service.recognize.assert_not_called()

    def test_background_generation_becomes_stale_after_mic_off(self):
        service = self.make_service()
        generation = service._current_input_generation()

        self.assertTrue(service._background_input_is_current(generation))
        service.settings.wake_listener_enabled = False
        service.cancel_pending_input()

        self.assertFalse(service._background_input_is_current(generation))

    def test_groq_speech_is_primary_recognizer(self):
        service = self.make_service()
        service.groq_transcriber = Mock(
            enabled=True,
            transcribe_audio=Mock(return_value="prakash ko message karo"),
        )
        service.recognizer.recognize_google = Mock(
            side_effect=AssertionError("Google fallback must not run")
        )
        self.assertEqual(
            service.recognize(object()),
            "prakash ko message karo",
        )

    def test_plain_wake_phrase_bypasses_startup_replay_guard(self):
        service = self.make_service()
        service.replay_guard = Mock()

        accepted, reason = service._accept_background_trigger(
            "Hey Aksh",
            wake_found=True,
            command="",
        )

        self.assertTrue(accepted)
        self.assertEqual(reason, "wake_only")
        service.replay_guard.arm_continuous_session.assert_called_once_with()
        service.replay_guard.allow.assert_not_called()

    def test_continuous_command_uses_replay_guard(self):
        service = self.make_service()
        service.replay_guard = Mock(
            allow=Mock(return_value=(False, "startup_grace"))
        )

        result = service._accept_background_trigger(
            "Chrome kholo",
            wake_found=False,
            command="",
        )

        self.assertEqual(result, (False, "startup_grace"))
        service.replay_guard.allow.assert_called_once_with(
            "Chrome kholo", explicit_wake=False
        )

    def test_spoken_mic_off_phrases(self):
        self.assertTrue(is_mic_off_command("mic off kar lo"))
        self.assertTrue(is_mic_off_command("mic off karo"))
        self.assertTrue(is_mic_off_command("mik off kro"))
        self.assertTrue(is_mic_off_command("Aksh maik ko band kar do"))
        self.assertTrue(is_mic_off_command("deactivate yourself"))
        self.assertTrue(is_mic_off_command("listening band karo"))
        self.assertFalse(is_mic_off_command("mic off mat karo"))
        self.assertFalse(is_mic_off_command("Chrome kholo"))

    def test_mic_off_bypasses_brain_and_disables_listener(self):
        brain = Mock()
        set_mic = Mock()
        processor = CommandProcessor(
            brain=brain,
            actions=Mock(),
            security=Mock(),
            confirmations=Mock(pending_action=None),
            friend_mode=Mock(),
            set_mic=set_mic,
            status=Mock(),
            say=Mock(),
            message=Mock(),
            stop_speaking=Mock(),
        )
        processor.process(
            "mic off karo", is_owner=True, source="typed"
        )
        set_mic.assert_called_once_with(False)
        brain.understand.assert_not_called()

    def test_clarification_marks_voice_followup_required(self):
        brain = Mock()
        brain.understand.return_value = BrainResponse(
            "Kaunsa gaana sunna hai?",
            needs_clarification=True,
        )
        actions = Mock()
        actions.shopping.followup.return_value = None
        actions.web.followup.return_value = None
        processor = CommandProcessor(
            brain=brain,
            actions=actions,
            security=Mock(),
            confirmations=Mock(pending_action=None),
            friend_mode=Mock(),
            set_mic=Mock(),
            status=Mock(),
            say=Mock(),
            message=Mock(),
            stop_speaking=Mock(),
        )

        processor.process("koi gaana chalao", is_owner=True, source="double-clap")

        self.assertTrue(processor.needs_voice_followup)


if __name__ == "__main__":
    unittest.main()
