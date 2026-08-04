import unittest

from backend.assistant import AkshAssistant
from backend.config import AkshSettings


class WakeCommandTests(unittest.TestCase):
    def test_command_can_follow_wake_phrase_in_same_sentence(self):
        assistant = object.__new__(AkshAssistant)
        assistant.settings = AkshSettings()
        self.assertEqual(
            assistant._command_after_wake("Hey Aksh, Chrome kholo"),
            "Chrome kholo",
        )

    def test_plain_wake_phrase_has_no_inline_command(self):
        assistant = object.__new__(AkshAssistant)
        assistant.settings = AkshSettings()
        self.assertEqual(assistant._command_after_wake("Hey Aksh"), "")

    def test_real_microphone_misrecognition_x_is_supported(self):
        assistant = object.__new__(AkshAssistant)
        assistant.settings = AkshSettings()
        self.assertEqual(
            assistant._command_after_wake("X Chrome kholo"),
            "Chrome kholo",
        )


if __name__ == "__main__":
    unittest.main()
