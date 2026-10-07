import unittest
from unittest.mock import Mock

from frontend.desktop.settings_ui import SettingsPanel, SlideSwitch


class SlideSwitchTests(unittest.TestCase):
    def test_changed_value_redraws_and_notifies(self):
        switch = object.__new__(SlideSwitch)
        switch._value = False
        switch._command = Mock()
        switch._draw = Mock()
        switch.focus_get = Mock(return_value=None)

        switch.set(True, notify=True)

        self.assertTrue(switch.value)
        switch._draw.assert_called_once_with(focused=False)
        switch._command.assert_called_once_with(True)

    def test_same_value_does_not_notify(self):
        switch = object.__new__(SlideSwitch)
        switch._value = True
        switch._command = Mock()
        switch._draw = Mock()
        switch.focus_get = Mock(return_value=None)

        switch.set(True, notify=True)

        switch._command.assert_not_called()


class SettingsPanelTests(unittest.TestCase):
    def test_switch_change_uses_matching_callback_and_refreshes(self):
        panel = object.__new__(SettingsPanel)
        panel.callbacks = {"wake": Mock()}
        panel.refresh = Mock()

        panel._changed("wake", False)

        panel.callbacks["wake"].assert_called_once_with(False)
        panel.refresh.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
