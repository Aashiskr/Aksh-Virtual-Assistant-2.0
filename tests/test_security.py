import unittest

from backend.models import ActionRequest, Sensitivity
from backend.security import SecurityManager


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.security = SecurityManager()

    def test_default_is_owner_only(self):
        self.assertTrue(self.security.speaker_is_allowed(True))
        self.assertFalse(self.security.speaker_is_allowed(False))

    def test_only_owner_can_enable_friends_mode(self):
        self.assertFalse(
            self.security.set_friends_mode(True, requested_by_owner=False)
        )
        self.assertFalse(self.security.friends_mode)
        self.assertTrue(
            self.security.set_friends_mode(True, requested_by_owner=True)
        )
        self.assertTrue(self.security.speaker_is_allowed(False))

    def test_friend_sensitive_action_needs_permission(self):
        self.security.set_friends_mode(True, requested_by_owner=True)
        action = ActionRequest("whatsapp_message")
        self.assertTrue(
            self.security.needs_owner_approval(action, is_owner=False)
        )
        self.assertTrue(
            self.security.needs_owner_approval(action, is_owner=True)
        )

    def test_dangerous_always_needs_confirmation(self):
        action = ActionRequest("system_action", {"option": "shutdown"})
        self.assertEqual(self.security.sensitivity(action), Sensitivity.DANGEROUS)
        self.assertTrue(self.security.needs_owner_approval(action, is_owner=True))

    def test_approval_phrase_is_exact(self):
        self.assertTrue(self.security.is_affirmative("Yes, allow".replace(",", "")))
        self.assertTrue(self.security.is_affirmative("haan karo"))
        self.assertFalse(self.security.is_affirmative("maybe yes later"))

    def test_action_bearing_confirmation_is_not_confirmation_only(self):
        self.assertTrue(self.security.is_confirmation_only("confirm"))
        self.assertFalse(
            self.security.is_confirmation_only(
                "Sudhir Sir ko call karo confirmed"
            )
        )


if __name__ == "__main__":
    unittest.main()
