import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.audio.output_guard import mute_output_while_listening
from backend.voice_session import VoiceCommandSession


class OutputGuardTests(unittest.TestCase):
    @patch("backend.voice_session.mute_output_while_listening")
    def test_voice_session_guards_command_capture(self, guard):
        settings = SimpleNamespace(
            voice_lock_enabled=False,
            mute_output_while_listening=True,
        )
        voice = Mock()
        capture = object()
        voice.listen_for_command.return_value = capture
        handle = Mock(return_value=False)
        session = VoiceCommandSession(
            settings,
            voice,
            Mock(enrolled=True),
            Mock(),
            Mock(),
            Mock(),
            handle,
        )

        session.run("double-clap")

        guard.assert_called_once_with(True)
        handle.assert_called_once_with(capture, "double-clap")

    @patch("backend.voice_session.mute_output_while_listening")
    def test_clarification_question_automatically_listens_for_answer(self, guard):
        settings = SimpleNamespace(
            voice_lock_enabled=False,
            mute_output_while_listening=True,
            voice_followup_turn_limit=3,
        )
        first_capture, answer_capture = object(), object()
        voice = Mock()
        voice.listen_for_command.side_effect = [first_capture, answer_capture]
        handle = Mock(side_effect=[True, False])
        speaker = Mock()
        session = VoiceCommandSession(
            settings,
            voice,
            Mock(enrolled=True),
            speaker,
            Mock(),
            Mock(),
            handle,
        )

        session.run("double-clap")

        self.assertEqual(voice.listen_for_command.call_count, 2)
        self.assertEqual(
            [call.args for call in handle.call_args_list],
            [(first_capture, "double-clap"), (answer_capture, "double-clap")],
        )
        speaker.wait_until_idle.assert_called_once_with(timeout=30.0)
        self.assertEqual(guard.call_count, 2)

    @patch("backend.audio.output_guard._speaker_endpoint")
    def test_output_is_muted_and_restored(self, endpoint_factory):
        endpoint = Mock()
        endpoint.GetMute.return_value = 0
        endpoint_factory.return_value = endpoint

        with mute_output_while_listening():
            endpoint.SetMute.assert_called_once_with(1, None)

        self.assertEqual(
            endpoint.SetMute.call_args_list[-1].args,
            (0, None),
        )

    @patch("backend.audio.output_guard._speaker_endpoint")
    def test_existing_mute_state_is_not_changed(self, endpoint_factory):
        endpoint = Mock()
        endpoint.GetMute.return_value = 1
        endpoint_factory.return_value = endpoint

        with mute_output_while_listening():
            pass

        endpoint.SetMute.assert_not_called()

    @patch("backend.audio.output_guard._speaker_endpoint")
    def test_disabled_guard_does_not_open_audio_endpoint(self, endpoint_factory):
        with mute_output_while_listening(False):
            pass

        endpoint_factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
