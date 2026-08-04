import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from backend.assistant import AkshAssistant
from frontend.desktop.app import AkshPetApp


class PetInteractionTests(unittest.TestCase):
    def test_single_click_greeting_says_namaste(self):
        assistant = object.__new__(AkshAssistant)
        assistant._closing = Mock()
        assistant._closing.is_set.return_value = False
        assistant._say = Mock()

        assistant.greet()

        assistant._say.assert_called_once_with("नमस्ते")

    def test_greeting_is_ignored_while_closing(self):
        assistant = object.__new__(AkshAssistant)
        assistant._closing = Mock()
        assistant._closing.is_set.return_value = True
        assistant._say = Mock()

        assistant.greet()

        assistant._say.assert_not_called()

    def test_pet_activation_turns_microphone_on_before_listening(self):
        app = object.__new__(AkshPetApp)
        app.settings = SimpleNamespace(wake_listener_enabled=False)
        app.wake_variable = Mock()
        app.store = Mock()
        app.assistant = Mock()

        app._activate("pet")

        app.wake_variable.set.assert_called_once_with(True)
        app.store.update.assert_called_once_with(wake_listener_enabled=True)
        app.assistant.activate.assert_called_once_with("pet")


if __name__ == "__main__":
    unittest.main()
