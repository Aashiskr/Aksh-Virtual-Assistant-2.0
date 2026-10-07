import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.actions.web_media import WebMediaActions
from backend.config import AkshSettings


class YouTubePlaybackTests(unittest.TestCase):
    def setUp(self):
        self.actions = WebMediaActions(AkshSettings())

    @patch("backend.actions.web_media.webbrowser.open")
    @patch("backend.actions.web_media.default_browser_name", return_value="chrome")
    @patch.object(WebMediaActions, "_reuse_active_youtube_tab", return_value=False)
    @patch.object(
        WebMediaActions,
        "_resolve_youtube_video_url",
        return_value="https://www.youtube.com/watch?v=abcdefghijk&autoplay=1",
    )
    def test_default_browser_opens_resolved_video_not_search(
        self,
        resolve,
        reuse_tab,
        default_browser,
        open_url,
    ):
        result = self.actions.youtube_play({"query": "good hindi songs"})
        self.assertTrue(result.success)
        open_url.assert_called_once_with(
            "https://www.youtube.com/watch?v=abcdefghijk&autoplay=1",
            new=0,
        )
        self.assertNotIn("results?search_query", open_url.call_args.args[0])
        self.assertEqual(self.actions._last_youtube_browser, "chrome")

    @patch("backend.actions.web_media.time.sleep")
    @patch(
        "backend.capabilities.media.active_browser_url",
        return_value="https://www.youtube.com/watch?v=oldvideo123",
    )
    @patch("backend.actions.web_media.active_browser_name", return_value="chrome")
    def test_background_youtube_tab_is_selected_and_reused(
        self,
        browser_name,
        active_url,
        sleep,
    ):
        gui = Mock()
        target = "https://www.youtube.com/watch?v=abcdefghijk&autoplay=1"
        with patch.dict("sys.modules", {"pyautogui": gui}):
            reused = WebMediaActions._reuse_active_youtube_tab(target)

        self.assertTrue(reused)
        gui.hotkey.assert_any_call("ctrl", "shift", "a")
        gui.write.assert_any_call("youtube", interval=0.02)
        gui.hotkey.assert_any_call("ctrl", "l")
        gui.write.assert_any_call(target, interval=0.01)

    @patch("backend.actions.web_media.time.sleep")
    @patch(
        "backend.capabilities.media.active_browser_url",
        return_value="https://www.youtube.com/watch?v=oldvideo123",
    )
    @patch("backend.capabilities.windows.switch_to_app", return_value=True)
    @patch(
        "backend.actions.web_media.active_browser_name",
        side_effect=["chrome", "brave"],
    )
    def test_previous_brave_youtube_tab_is_reused_while_chrome_is_active(
        self,
        browser_name,
        switch_to_app,
        active_url,
        sleep,
    ):
        gui = Mock()
        target = "https://www.youtube.com/watch?v=abcdefghijk&autoplay=1"
        with patch.dict("sys.modules", {"pyautogui": gui}):
            reused = WebMediaActions._reuse_active_youtube_tab(
                target,
                browser_name="brave",
            )

        self.assertTrue(reused)
        switch_to_app.assert_called_once_with("brave")
        gui.hotkey.assert_any_call("ctrl", "shift", "a")
        gui.hotkey.assert_any_call("ctrl", "l")
        gui.write.assert_any_call(target, interval=0.01)

    @patch("backend.actions.web_media.subprocess.Popen")
    @patch.object(
        WebMediaActions,
        "_find_browser_executable",
        return_value=Path("C:/Brave/brave.exe"),
    )
    @patch.object(
        WebMediaActions,
        "_resolve_youtube_video_url",
        return_value="https://www.youtube.com/watch?v=abcdefghijk&autoplay=1",
    )
    def test_explicit_brave_opens_resolved_video_in_brave(
        self,
        resolve,
        find_browser,
        popen,
    ):
        # Never let this unit test drive the user's real Brave window. The
        # production path first tries to reuse an existing YouTube tab, which
        # uses keyboard automation when it is not explicitly isolated here.
        with patch.object(
            WebMediaActions,
            "_reuse_active_youtube_tab",
            return_value=False,
        ):
            result = self.actions.youtube_play(
                {"query": "good hindi songs", "target": "brave"}
            )
        self.assertTrue(result.success)
        find_browser.assert_called_once_with("brave")
        popen.assert_called_once_with(
            [
                "C:\\Brave\\brave.exe",
                "https://www.youtube.com/watch?v=abcdefghijk&autoplay=1",
            ]
        )
        self.assertIn("Brave", result.message)


class WebsiteBrowserRoutingTests(unittest.TestCase):
    def setUp(self):
        self.actions = WebMediaActions(AkshSettings())

    @patch("backend.actions.web_media.subprocess.Popen")
    @patch.object(
        WebMediaActions,
        "_find_browser_executable",
        return_value=Path("C:/Brave/brave.exe"),
    )
    def test_explicit_brave_owns_website_url(self, find_browser, popen):
        result = self.actions.open_website(
            {"target": "dezignbank.com", "browser": "brave"}
        )
        self.assertTrue(result.success)
        find_browser.assert_called_once_with("brave")
        popen.assert_called_once_with(
            ["C:\\Brave\\brave.exe", "https://dezignbank.com"]
        )
        self.assertIn("Brave", result.message)


if __name__ == "__main__":
    unittest.main()
