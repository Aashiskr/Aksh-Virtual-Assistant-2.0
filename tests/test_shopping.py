import unittest
from unittest.mock import Mock

from backend.brain.fallback import local_intent
from backend.config import AkshSettings
from backend.models import ActionRequest, Sensitivity
from backend.security import SecurityManager
from backend.shopping.controller import ShoppingActions


class ShoppingTests(unittest.TestCase):
    def make_actions(self):
        actions = ShoppingActions(AkshSettings())
        actions.browser = Mock()
        actions.browser.active = True
        return actions

    def test_hinglish_clothes_search_routes_to_shopping(self):
        response = local_intent("mere liye black kapde dhundo")
        action = response.actions[0]
        self.assertEqual(action.name, "shopping")
        self.assertEqual(action.parameters["option"], "search")
        self.assertIn("black", action.parameters["query"])

    def test_active_session_understands_next_and_stop(self):
        actions = self.make_actions()
        self.assertEqual(
            actions.followup("ye nahi pasand next dikhao").parameters["option"],
            "next",
        )
        self.assertEqual(
            actions.followup("bas band karo nahi dekhna").parameters["option"],
            "stop",
        )

    def test_cart_command_targets_current_product(self):
        actions = self.make_actions()
        action = actions.followup("is wale ko cart me dalo")
        self.assertEqual(action.parameters["option"], "add_cart")

    def test_only_add_cart_is_sensitive(self):
        safe = ActionRequest("shopping", {"option": "next"})
        cart = ActionRequest("shopping", {"option": "add_cart"})
        self.assertEqual(SecurityManager.sensitivity(safe), Sensitivity.SAFE)
        self.assertEqual(
            SecurityManager.sensitivity(cart), Sensitivity.SENSITIVE
        )


if __name__ == "__main__":
    unittest.main()
