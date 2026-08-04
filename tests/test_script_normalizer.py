import unittest
from unittest.mock import Mock

from backend.brain.groq import GroqBrain
from backend.config import AkshSettings
from backend.integrations.groq_speech import GroqSpeechTranscriber
from backend.integrations.script_normalizer import (
    ScriptNormalizer,
    contains_urdu_script,
)


class ScriptNormalizerTests(unittest.TestCase):
    def make_normalizer(self):
        settings = AkshSettings(groq_api_key="gsk_test_key")
        normalizer = ScriptNormalizer(settings)
        normalizer.client = Mock()
        return normalizer

    def test_latin_text_is_not_sent_to_groq_again(self):
        normalizer = self.make_normalizer()
        self.assertEqual(normalizer.normalize("call Khushi"), "call Khushi")
        normalizer.client.post.assert_not_called()

    def test_urdu_command_is_rewritten_as_roman_hinglish(self):
        normalizer = self.make_normalizer()
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": "Khushi ko call karo"}}]
        }
        normalizer.client.post.return_value = response
        result = normalizer.normalize("خوشی کو کال کرو")
        self.assertEqual(result, "Khushi ko call karo")
        response.raise_for_status.assert_called_once_with()

    def test_local_fallback_never_leaks_urdu_script(self):
        normalizer = self.make_normalizer()
        normalizer.client.post.side_effect = RuntimeError("offline")
        result = normalizer.normalize("خوشی کو کال کرو")
        self.assertFalse(contains_urdu_script(result))
        self.assertEqual(result, "Khushi ko call karo")

    def test_speech_transcriber_normalizes_phone_and_laptop_audio(self):
        transcriber = GroqSpeechTranscriber(AkshSettings(groq_api_key="gsk_test"))
        response = Mock()
        response.json.return_value = {"text": "خوشی کو کال کرو"}
        transcriber.client = Mock()
        transcriber.client.post.return_value = response
        transcriber.script_normalizer = Mock(
            normalize=Mock(return_value="Khushi ko call karo")
        )
        result = transcriber._transcribe("command.wav", b"audio", "audio/wav")
        self.assertEqual(result, "Khushi ko call karo")
        transcriber.script_normalizer.normalize.assert_called_once_with(
            "خوشی کو کال کرو"
        )

    def test_brain_sanitizes_reply_and_contact_parameter(self):
        brain = GroqBrain(AkshSettings(groq_api_key="gsk_test"))
        brain.script_normalizer = Mock()
        brain.script_normalizer.normalize.side_effect = {
            "میں کال کر رہا ہوں": "Main call kar raha hoon",
            "خوشی": "Khushi",
        }.get
        result = brain._validate_response(
            {
                "spoken_reply": "میں کال کر رہا ہوں",
                "needs_clarification": False,
                "actions": [
                    {
                        "name": "whatsapp_call",
                        "parameters": {"contact": "خوشی"},
                    }
                ],
            }
        )
        self.assertEqual(result.spoken_reply, "Main call kar raha hoon")
        self.assertEqual(result.actions[0].parameters["contact"], "Khushi")


if __name__ == "__main__":
    unittest.main()
