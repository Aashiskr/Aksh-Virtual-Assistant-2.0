import unittest

from frontend.desktop.hotkey import GlobalHotkey


class HotkeyTests(unittest.TestCase):
    def test_human_readable_hotkey_is_normalized_for_pynput(self):
        hotkey = GlobalHotkey("ctrl+alt+k", lambda: None)
        self.assertEqual(hotkey._pynput_expression(), "<ctrl>+<alt>+k")


if __name__ == "__main__":
    unittest.main()
