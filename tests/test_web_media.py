import unittest
from pathlib import Path
from unittest.mock import patch

from backend.actions.web_media import WebMediaActions
from backend.config import AkshSettings


class YouTubePlaybackTests(unittest.TestCase):
    def setUp(self):
        self.actions = WebMediaActions(AkshSettings())

    @patch("backend.actions.web_media.webbrowser.open")
    @patch.object(
        WebMediaActions,
        "_resolve_youtube_video_url",
        return_value="https://www.youtube.com/watch?v=abcdefghijk&autoplay=1",
    )
    def test_default_browser_opens_resolved_video_not_search(
        self,
        resolve,
        open_url,
    ):
        result = self.actions.youtube_play({"query": "good hindi songs"})
        self.assertTrue(result.success)
        open_url.assert_called_once_with(
            "https://www.youtube.com/watch?v=abcdefghijk&autoplay=1"
        )
        self.assertNotIn("results?search_query", open_url.call_args.args[0])

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
