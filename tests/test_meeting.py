import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import numpy as np

from backend.assistant import AkshAssistant
from backend.config import AkshSettings
from backend.meeting.audio_capture import AudioSegmenter
from backend.meeting.brain import MeetingBrain, _parse_json_object, _text_chunks
from backend.meeting.controller import MeetingController
from backend.meeting.models import ReplyReview
from backend.meeting.session import MeetingSession
from backend.audio.speaker import Speaker
from frontend.desktop.meeting_ui import MeetingUI


class MeetingSessionTests(unittest.TestCase):
    def test_report_keeps_transcript_questions_and_owner_reply(self):
        with tempfile.TemporaryDirectory() as folder:
            session = MeetingSession(Path(folder))
            session.add_turn("participant", "What is dependency injection?")
            session.add_turn("owner", "It creates every dependency internally.")
            exchange = session.add_exchange(
                "What is dependency injection?",
                "Dependencies are provided from outside.",
                ["Loose coupling", "Testability"],
            )
            session.record_reply(
                exchange,
                "It creates every dependency internally.",
                ReplyReview(
                    True,
                    "Dependencies are not created internally.",
                    "They are supplied from outside the class.",
                ),
            )
            markdown_path, json_path, markdown = session.finish(
                {
                    "summary": "Dependency injection discussion.",
                    "key_points": ["Loose coupling"],
                    "decisions": [],
                    "action_items": [],
                    "follow_ups": [],
                }
            )
            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())
            self.assertIn("Your reply", markdown)
            self.assertIn("Better answer", markdown)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["turns"]), 2)
            self.assertEqual(len(payload["exchanges"]), 1)


class MeetingBrainTests(unittest.TestCase):
    def test_question_candidate_covers_direct_and_interview_requests(self):
        self.assertTrue(MeetingBrain.looks_like_question("What is an API?"))
        self.assertTrue(
            MeetingBrain.looks_like_question("Tell me about yourself")
        )
        self.assertFalse(
            MeetingBrain.looks_like_question("The deployment finished today")
        )

    def test_long_meeting_is_chunked_from_start_to_finish(self):
        transcript = "\n".join(f"Turn {index}: detail" for index in range(80))
        chunks = _text_chunks(transcript, 180)
        self.assertGreater(len(chunks), 1)
        rebuilt = "\n".join(chunks)
        self.assertIn("Turn 0: detail", rebuilt)
        self.assertIn("Turn 79: detail", rebuilt)

    def test_question_response_is_validated(self):
        brain = MeetingBrain(AkshSettings(groq_api_key="gsk_test"))
        brain.profile = Mock()
        brain.profile.context.return_value = "Python developer profile"
        response = Mock()
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "is_question": True,
                                "question": "What is an API?",
                                "answer": "An API is a software interface.",
                                "key_points": ["Contract", "Integration"],
                            }
                        )
                    }
                }
            ]
        }
        brain.client = Mock()
        brain.client.post.return_value = response
        result = brain.suggest_answer("What is an API?", "Participant asked")
        self.assertEqual(result[1], "An API is a software interface.")
        response.raise_for_status.assert_called_once_with()
        request = brain.client.post.call_args.kwargs["json"]
        self.assertIn(
            "Python developer profile",
            request["messages"][1]["content"],
        )
        self.assertEqual(request["response_format"]["type"], "json_schema")

    def test_json_validation_400_retries_without_forcing_json_mode(self):
        brain = MeetingBrain(AkshSettings(groq_api_key="gsk_test"))
        brain.profile = Mock()
        brain.profile.context.return_value = ""
        bad_schema = Mock(status_code=400)
        bad_json_mode = Mock(status_code=400)
        plain = Mock(status_code=200)
        plain.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "is_question": True,
                                "question": "What is an API?",
                                "answer": "A software interface.",
                                "key_points": [],
                            }
                        )
                    }
                }
            ]
        }
        brain.client = Mock()
        brain.client.post.side_effect = [bad_schema, bad_json_mode, plain]

        result = brain.suggest_answer("What is an API?", "")

        self.assertEqual(result[1], "A software interface.")
        requests = brain.client.post.call_args_list
        self.assertEqual(len(requests), 3)
        self.assertNotIn("response_format", requests[2].kwargs["json"])
        plain.raise_for_status.assert_called_once_with()

    def test_json_object_can_be_extracted_from_fenced_response(self):
        value = _parse_json_object('Result:\n```json\n{"ok": true}\n```')
        self.assertEqual(value, {"ok": True})


class AudioSegmenterTests(unittest.TestCase):
    def test_continuous_audio_is_split_only_after_trailing_silence(self):
        rate, frames = 16000, 800
        segmenter = AudioSegmenter(
            rate,
            frames,
            minimum_level=0.01,
            trailing_silence=0.15,
        )
        speech = (
            np.full(frames, 5000, dtype=np.int16).tobytes()
        )
        silence = np.zeros(frames, dtype=np.int16).tobytes()
        outputs = []
        chunks = [silence, *([speech] * 10), silence, silence, silence]
        for chunk in chunks:
            result = segmenter.feed(chunk)
            if result:
                outputs.append(result)
        self.assertEqual(len(outputs), 1)
        self.assertGreater(len(outputs[0]), len(speech) * 2)

    def test_occasional_microphone_noise_spikes_are_not_speech(self):
        rate, frames = 16000, 800
        segmenter = AudioSegmenter(
            rate,
            frames,
            minimum_level=0.01,
            trailing_silence=0.15,
        )
        quiet = np.full(frames, 200, dtype=np.int16).tobytes()
        spike = np.full(frames, 900, dtype=np.int16).tobytes()
        outputs = []
        for index in range(40):
            result = segmenter.feed(spike if index % 10 == 0 else quiet)
            if result:
                outputs.append(result)
        self.assertEqual(outputs, [])
        self.assertIsNone(segmenter.flush())


class MeetingControllerTests(unittest.TestCase):
    def make_controller(self, folder):
        events = []
        controller = MeetingController(
            AkshSettings(groq_api_key="gsk_test"),
            lambda event, payload: events.append((event, payload)),
        )
        controller.session = MeetingSession(Path(folder))
        return controller, events

    def test_participant_question_gets_answer_but_owner_voice_gets_review(self):
        with tempfile.TemporaryDirectory() as folder:
            controller, events = self.make_controller(folder)
            controller.transcriber = Mock()
            controller.brain = Mock()
            controller.transcriber.transcribe.side_effect = [
                "What is dependency injection?",
                "It means creating everything inside the class.",
            ]
            controller.brain.suggest_answer.return_value = (
                "What is dependency injection?",
                "Dependencies are supplied from outside.",
                ["Loose coupling"],
            )
            controller.brain.review_reply.return_value = ReplyReview(
                True,
                "That reverses the definition.",
                "Dependencies are supplied from outside.",
            )
            controller._process_turn("participant", b"participant")
            controller._process_turn("owner", b"owner")
            controller.brain.suggest_answer.assert_called_once()
            controller.brain.review_reply.assert_called_once()
            self.assertEqual(
                [event for event, _ in events],
                ["transcript", "answer", "transcript", "reply_review"],
            )
            exchange = controller.session.exchanges[0]
            self.assertIn("creating everything", exchange.owner_reply)
            self.assertTrue(exchange.correction)

    def test_question_split_across_audio_chunks_still_gets_answer(self):
        with tempfile.TemporaryDirectory() as folder:
            controller, events = self.make_controller(folder)
            controller.transcriber = Mock()
            controller.brain = Mock()
            controller.transcriber.transcribe.side_effect = [
                "Let us move to the next interview topic",
                "Can you explain dependency injection",
            ]
            controller.brain.suggest_answer.side_effect = [
                None,
                (
                    "Can you explain dependency injection?",
                    "Dependencies are supplied from outside.",
                    ["Loose coupling"],
                ),
            ]
            controller._process_turn("participant", b"first")
            controller._process_turn("participant", b"second")
            self.assertEqual(len(controller.session.exchanges), 1)
            self.assertIn(
                "Let us move",
                controller.brain.suggest_answer.call_args_list[1].args[0],
            )
            self.assertIn("answer", [event for event, _ in events])


class MeetingSilenceTests(unittest.TestCase):
    def test_normal_speech_is_suppressed_during_meeting(self):
        assistant = object.__new__(AkshAssistant)
        assistant._meeting_mode = True
        assistant.message_callback = Mock()
        assistant.speaker = Mock()
        assistant._say("This must stay silent")
        assistant.message_callback.assert_not_called()
        assistant.speaker.speak.assert_not_called()

    def test_menu_label_tracks_meeting_state(self):
        ui = object.__new__(MeetingUI)
        ui.assistant = Mock(meeting_active=False)
        self.assertEqual(ui._menu_label(), "Start Meeting Mode")
        ui.assistant.meeting_active = True
        self.assertEqual(ui._menu_label(), "Stop Meeting Mode")

    def test_answer_event_is_saved_and_shown(self):
        ui = object.__new__(MeetingUI)
        ui.overlay = Mock()
        ui.menu = None
        ui.menu_index = None
        ui.last_answer_index = None
        ui.last_answer = None
        payload = {
            "question": "What is an API?",
            "answer": "A software interface.",
            "key_points": ["Contract"],
        }
        ui.handle("answer", payload)
        self.assertEqual(ui.last_answer, payload)
        ui.overlay.show_answer.assert_called_once_with(
            "What is an API?",
            "A software interface.",
            ["Contract"],
        )

    def test_speaker_drops_new_items_while_meeting_muted(self):
        speaker = object.__new__(Speaker)
        speaker._muted = Mock()
        speaker._muted.is_set.return_value = True
        speaker._queue = Mock()
        speaker.speak("Must not enter queue")
        speaker._queue.put.assert_not_called()


if __name__ == "__main__":
    unittest.main()
