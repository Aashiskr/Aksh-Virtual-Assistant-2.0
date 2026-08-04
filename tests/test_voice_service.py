import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from backend.audio import VoicePrintManager, VoiceService, is_mic_off_command
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


if __name__ == "__main__":
    unittest.main()
