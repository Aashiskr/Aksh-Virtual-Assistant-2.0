import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from backend.command_processor import CommandProcessor
from backend.confirmations import ConfirmationManager
from backend.config import AkshSettings
from backend.models import ActionRequest, ActionResult, BrainResponse
from backend.security import SecurityManager


class ConfirmationManagerTests(unittest.TestCase):
    def make_manager(self, *, now=10.0, timeout=90.0):
        clock = Mock(return_value=now)
        manager = ConfirmationManager(
            AkshSettings(confirmation_timeout_seconds=timeout),
            SecurityManager(),
            Mock(),
            Mock(),
            clock=clock,
        )
        return manager, clock

    def test_confirm_and_allowed_approve_pending_action(self):
        for phrase in ("confirm", "allowed", "yes confirm", "haan kar do"):
            with self.subTest(phrase=phrase):
                manager, _ = self.make_manager()
                action = ActionRequest("system_action", {"option": "shutdown"})
                manager.request(action, source="phone")
                result = manager.resolve(phrase, is_owner=True)
                self.assertEqual(result.state, "approved")
                self.assertIs(result.action, action)
                self.assertIsNone(manager.pending_action)

    def test_cancel_clears_pending_action(self):
        manager, _ = self.make_manager()
        manager.request(
            ActionRequest("system_action", {"option": "restart"}),
            source="pet",
        )
        result = manager.resolve("cancel kar do", is_owner=True)
        self.assertEqual(result.state, "denied")
        self.assertIsNone(manager.pending_action)

    def test_non_owner_cannot_approve_but_request_stays_pending(self):
        manager, _ = self.make_manager()
        action = ActionRequest("system_action", {"option": "lock"})
        manager.request(action, source="wake")
        result = manager.resolve("confirm", is_owner=False)
        self.assertEqual(result.state, "unauthorized")
        self.assertIs(manager.pending_action, action)

    def test_expired_confirmation_never_executes(self):
        manager, clock = self.make_manager(now=10.0, timeout=30.0)
        manager.request(
            ActionRequest("system_action", {"option": "sleep"}),
            source="phone",
        )
        clock.return_value = 41.0
        result = manager.resolve("confirm", is_owner=True)
        self.assertEqual(result.state, "expired")
        self.assertIsNone(result.action)

    def test_action_bearing_confirmation_does_not_approve_old_request(self):
        manager, _ = self.make_manager()
        action = ActionRequest(
            "whatsapp_call",
            {"contact": "sadir se", "platform": "desktop"},
        )
        manager.request(action, source="phone")
        result = manager.resolve(
            "Sudhir Sir ko call kro confirmed",
            is_owner=True,
        )
        self.assertEqual(result.state, "waiting")
        self.assertIsNone(result.action)
        self.assertIs(manager.pending_action, action)


class ConfirmationFlowTests(unittest.TestCase):
    def make_processor(self, option):
        security = SecurityManager()
        settings = AkshSettings(confirmation_timeout_seconds=90.0)
        confirmations = ConfirmationManager(
            settings, security, Mock(), Mock()
        )
        brain = Mock(
            understand=Mock(
                return_value=BrainResponse(
                    actions=[
                        ActionRequest("system_action", {"option": option})
                    ]
                )
            )
        )
        actions = Mock()
        actions.shopping = SimpleNamespace(followup=lambda text: None)
        actions.execute.return_value = ActionResult(
            True, f"{option} safely simulated"
        )
        processor = CommandProcessor(
            brain=brain,
            actions=actions,
            security=security,
            confirmations=confirmations,
            friend_mode=Mock(),
            set_mic=Mock(),
            status=Mock(),
            say=Mock(),
            message=Mock(),
            stop_speaking=Mock(),
        )
        return processor, actions

    def test_all_system_actions_use_same_two_command_flow(self):
        for option in ("shutdown", "restart", "lock", "sleep"):
            for source in ("phone", "pet"):
                with self.subTest(option=option, source=source):
                    processor, actions = self.make_processor(option)
                    first = processor.process(
                        f"{option} the computer",
                        is_owner=True,
                        source=source,
                    )
                    self.assertIn("confirmation", first.lower())
                    actions.execute.assert_not_called()
                    second = processor.process(
                        "confirm", is_owner=True, source=source
                    )
                    self.assertEqual(second, f"{option} safely simulated")
                    actions.execute.assert_called_once()

    def make_call_processor(self):
        security = SecurityManager()
        confirmations = ConfirmationManager(
            AkshSettings(confirmation_timeout_seconds=90.0),
            security,
            Mock(),
            Mock(),
        )
        brain = Mock(
            understand=Mock(
                return_value=BrainResponse(
                    actions=[
                        ActionRequest(
                            "whatsapp_call",
                            {"contact": "sadir se", "platform": "desktop"},
                        )
                    ]
                )
            )
        )
        actions = Mock()
        actions.shopping = SimpleNamespace(followup=lambda text: None)
        actions.execute.side_effect = lambda action: ActionResult(
            True,
            f"called {action.parameters['contact']}",
        )
        processor = CommandProcessor(
            brain=brain,
            actions=actions,
            security=security,
            confirmations=confirmations,
            friend_mode=Mock(),
            set_mic=Mock(),
            status=Mock(),
            say=Mock(),
            message=Mock(),
            stop_speaking=Mock(),
        )
        return processor, actions, confirmations

    def test_repeated_call_command_replaces_misheard_pending_contact(self):
        processor, actions, confirmations = self.make_call_processor()
        processor.process(
            "sadir se ko call kro",
            is_owner=True,
            source="phone",
        )
        correction = processor.process(
            "Sudhir Sir ko call kro",
            is_owner=True,
            source="phone",
        )
        self.assertIn("sudhir sir", correction.lower())
        self.assertEqual(
            confirmations.pending_action.parameters["contact"],
            "sudhir sir",
        )
        actions.execute.assert_not_called()

        result = processor.process(
            "confirm",
            is_owner=True,
            source="phone",
        )
        self.assertEqual(result, "called sudhir sir")
        actions.execute.assert_called_once()

    def test_correction_with_confirmed_never_executes_old_contact(self):
        processor, actions, confirmations = self.make_call_processor()
        processor.process(
            "sadir se ko call kro",
            is_owner=True,
            source="phone",
        )
        result = processor.process(
            "Sudhir Sir ko call kro confirmed",
            is_owner=True,
            source="phone",
        )
        self.assertIn("alag se sirf confirm", result.lower())
        self.assertEqual(
            confirmations.pending_action.parameters["contact"],
            "sudhir sir",
        )
        actions.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
