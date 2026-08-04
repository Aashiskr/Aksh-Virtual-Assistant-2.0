import unittest
from unittest.mock import Mock

from frontend.desktop.pet_view import PetView


class PetStatusTests(unittest.TestCase):
    def make_view(self):
        view = object.__new__(PetView)
        view.canvas = Mock()
        view.root = Mock()
        view.animator = Mock()
        view.status_panel = 1
        view.name_text = 2
        view.mode_text = 3
        view.status_text = 4
        view._status_hide_job = None
        view._state = "idle"
        view._status = ""
        view._friends_mode = False
        view._voice_lock_enabled = False
        return view

    def assert_visibility(self, view, expected):
        state = "normal" if expected else "hidden"
        calls = [
            call
            for call in view.canvas.itemconfigure.call_args_list
            if "state" in call.kwargs
        ][-4:]
        self.assertEqual(
            [(call.args[0], call.kwargs["state"]) for call in calls],
            [(1, state), (2, state), (3, state), (4, state)],
        )

    def test_microphone_off_status_is_hidden(self):
        view = self.make_view()
        view.set_status("sleeping", "Microphone listening off", False, False)
        self.assert_visibility(view, False)

    def test_active_status_is_visible(self):
        view = self.make_view()
        view.set_status("listening", "Listening", False, False)
        self.assert_visibility(view, True)

    def test_message_is_temporarily_visible_then_hides_when_idle(self):
        view = self.make_view()
        callbacks = []
        view.root.after.side_effect = lambda delay, callback: (
            callbacks.append(callback) or "job"
        )

        view.show_message("assistant", "Done")
        self.assert_visibility(view, True)
        callbacks[0]()
        self.assert_visibility(view, False)


if __name__ == "__main__":
    unittest.main()
