import unittest

from backend.brain.groq import GroqBrain
from backend.brain.fallback import local_intent, priority_intent
from backend.models import ActionRequest


class BrainFallbackTests(unittest.TestCase):
    def test_owner_can_enable_friends_mode_phrase(self):
        result = priority_intent("Now you can also listen to my friends")
        self.assertIsNotNone(result)
        self.assertEqual(result.actions[0].name, "friend_mode")
        self.assertEqual(result.actions[0].parameters["option"], "on")

    def test_owner_can_disable_friends_mode_phrase(self):
        result = priority_intent("Stop listening to my friends")
        self.assertEqual(result.actions[0].parameters["option"], "off")

    def test_hinglish_open_app(self):
        result = local_intent("chrome kholo")
        self.assertEqual(result.actions[0].name, "open_app")
        self.assertEqual(result.actions[0].parameters["target"], "chrome")

    def test_explicit_browser_and_domain_become_one_website_action(self):
        result = local_intent("open and in brave open dezignbank.com")
        self.assertEqual(len(result.actions), 1)
        action = result.actions[0]
        self.assertEqual(action.name, "open_website")
        self.assertEqual(action.parameters["target"], "dezignbank.com")
        self.assertEqual(action.parameters["browser"], "brave")

    def test_model_browser_launch_is_merged_into_following_website(self):
        actions = GroqBrain._merge_browser_launch(
            [
                ActionRequest("open_app", {"target": "Brave"}),
                ActionRequest("open_website", {"target": "dezignbank.com"}),
            ]
        )
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].name, "open_website")
        self.assertEqual(actions[0].parameters["browser"], "brave")

    def test_media_intent(self):
        result = local_intent("play brown rang on spotify")
        self.assertEqual(result.actions[0].name, "spotify_play")
        self.assertEqual(result.actions[0].parameters["query"], "brown rang")

    def test_youtube_play_preserves_explicit_brave_browser(self):
        result = local_intent(
            "brave open kr ke youtube pe achhe hindi song chalao"
        )
        action = result.actions[0]
        self.assertEqual(action.name, "youtube_play")
        self.assertEqual(action.parameters["query"], "achhe hindi song")
        self.assertEqual(action.parameters["target"], "brave")

    def test_dangerous_intent_is_structured(self):
        result = local_intent("computer shutdown kar do")
        self.assertEqual(result.actions[0].name, "system_action")
        self.assertEqual(result.actions[0].parameters["option"], "shutdown")

    def test_sleep_intent_is_structured(self):
        result = local_intent("put computer to sleep")
        self.assertEqual(result.actions[0].name, "system_action")
        self.assertEqual(result.actions[0].parameters["option"], "sleep")

    def test_battery_is_priority_even_when_groq_is_enabled(self):
        result = priority_intent("battery kitni hai")
        self.assertEqual(result.actions[0].name, "battery_status")

    def test_shopping_start_is_priority_even_when_groq_is_enabled(self):
        result = priority_intent(
            "mere liye black oversized t shirt dhundo"
        )
        self.assertEqual(result.actions[0].name, "shopping")
        self.assertEqual(result.actions[0].parameters["option"], "search")

    def test_end_call_is_priority_even_when_groq_is_enabled(self):
        result = priority_intent("cut the call")
        self.assertEqual(result.actions[0].name, "whatsapp_end_call")
        self.assertEqual(result.actions[0].parameters["platform"], "desktop")

    def test_stop_call_is_not_mistaken_for_generic_stop(self):
        result = priority_intent("call stop kar do")
        self.assertEqual(result.actions[0].name, "whatsapp_end_call")


if __name__ == "__main__":
    unittest.main()
