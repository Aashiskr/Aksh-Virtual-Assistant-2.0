import unittest
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.assistant import AkshAssistant
from frontend.desktop.app import AkshPetApp


class PetInteractionTests(unittest.TestCase):
    @patch("backend.assistant.threading.Thread")
    def test_double_clap_activation_is_one_shot(self, worker):
        assistant = object.__new__(AkshAssistant)
        assistant.settings = SimpleNamespace(wake_listener_enabled=False)
        assistant._closing = Mock()
        assistant._closing.is_set.return_value = False
        assistant._meeting_mode = False
        assistant._active_lock = threading.Lock()
        assistant._status = Mock()
        assistant.set_wake_listener_enabled = Mock()
        assistant.voice = Mock()
        assistant.command_runtime = Mock()
        assistant.voice_session = Mock()

        assistant.activate("double-clap")

        assistant.set_wake_listener_enabled.assert_not_called()
        assistant.voice.arm_continuous_session.assert_not_called()
        worker.return_value.start.assert_called_once_with()

    def test_assistant_wires_double_clap_to_voice_activation(self):
        assistant = object.__new__(AkshAssistant)
        assistant.settings = SimpleNamespace(smart_environment_enabled=False)
        assistant.brain = Mock()
        assistant.actions = Mock()
        assistant.battery_monitor = Mock()
        assistant.environment_monitor = Mock()
        assistant.voice = Mock()
        assistant.security = SimpleNamespace(friends_mode=False)
        assistant._on_wake_phrase = Mock()
        assistant._status = Mock()
        assistant._show_idle_status = Mock()
        assistant.activate = Mock()

        assistant.start()
        clap_callback = assistant.voice.start_wake_listener.call_args.kwargs[
            "double_clap_callback"
        ]
        clap_callback()

        assistant.activate.assert_called_once_with("double-clap")

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

    def test_double_clap_menu_setting_is_persisted(self):
        app = object.__new__(AkshPetApp)
        app.double_clap_variable = Mock()
        app.double_clap_variable.get.return_value = True
        app.store = Mock()
        app.assistant = Mock()

        app._toggle_double_clap()

        app.store.update.assert_called_once_with(double_clap_enabled=True)
        app.assistant.set_double_clap_enabled.assert_called_once_with(True)

    def test_microphone_off_also_disables_double_clap_sensor(self):
        assistant = object.__new__(AkshAssistant)
        assistant.settings = SimpleNamespace(
            wake_listener_enabled=True,
            double_clap_enabled=True,
        )
        assistant.voice = Mock()
        assistant.speaker = Mock()
        assistant._show_idle_status = Mock()

        assistant.set_wake_listener_enabled(False)

        self.assertFalse(assistant.settings.wake_listener_enabled)
        self.assertFalse(assistant.settings.double_clap_enabled)
        assistant.voice.cancel_pending_input.assert_called_once_with()
        assistant.speaker.stop_current.assert_called_once_with()

    def test_microphone_menu_off_persists_master_off_state(self):
        app = object.__new__(AkshPetApp)
        app.wake_variable = Mock()
        app.double_clap_variable = Mock()
        app.store = Mock()
        app.assistant = Mock()
        app._refresh_microphone_menu = Mock()

        app._set_wake_enabled(False)

        app.wake_variable.set.assert_called_once_with(False)
        app.double_clap_variable.set.assert_called_once_with(False)
        app.store.update.assert_called_once_with(
            wake_listener_enabled=False,
            double_clap_enabled=False,
        )
        app.assistant.set_wake_listener_enabled.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
