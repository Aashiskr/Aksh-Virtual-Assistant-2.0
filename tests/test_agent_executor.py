import unittest
from unittest.mock import Mock

from backend.actions import ActionRegistry
from backend.agent.catalog import ACTION_NAMES, EXECUTOR_ACTION_NAMES
from backend.agent.executor import AgentExecutor
from backend.config import AkshSettings
from backend.confirmations import ConfirmationManager
from backend.models import ActionRequest, ActionResult
from backend.security import SecurityManager


class AgentExecutorTests(unittest.TestCase):
    def make_executor(self, *, max_steps=5):
        security = SecurityManager(confirm_sensitive_actions=True)
        confirmations = ConfirmationManager(
            AkshSettings(), security, Mock(), Mock()
        )
        actions = Mock()
        actions.execute.return_value = ActionResult(True, "done")
        executor = AgentExecutor(
            actions=actions,
            security=security,
            confirmations=confirmations,
            friend_mode=Mock(),
            status=Mock(),
            say=Mock(),
            stop_speaking=Mock(),
            max_steps=max_steps,
        )
        return executor, actions, confirmations

    def test_plan_runs_in_order(self):
        executor, actions, _ = self.make_executor()
        plan = [
            ActionRequest("open_app", {"target": "notepad"}),
            ActionRequest("battery_status"),
        ]
        executor.execute_plan(plan, is_owner=True, source="typed")
        self.assertEqual(
            [call.args[0].name for call in actions.execute.call_args_list],
            ["open_app", "battery_status"],
        )

    def test_failure_stops_remaining_steps(self):
        executor, actions, _ = self.make_executor()
        actions.execute.side_effect = [
            ActionResult(False, "failed"),
            ActionResult(True, "must not run"),
        ]
        executor.execute_plan(
            [ActionRequest("open_app"), ActionRequest("battery_status")],
            is_owner=True,
            source="typed",
        )
        actions.execute.assert_called_once()

    def test_confirmation_resumes_remaining_plan(self):
        executor, actions, confirmations = self.make_executor()
        plan = [
            ActionRequest("battery_status"),
            ActionRequest(
                "whatsapp_message",
                {"contact": "Abhay", "message": "hello"},
            ),
            ActionRequest("screenshot"),
        ]
        executor.execute_plan(plan, is_owner=True, source="phone")
        self.assertEqual(
            [call.args[0].name for call in actions.execute.call_args_list],
            ["battery_status"],
        )
        resolution = confirmations.resolve("confirm", is_owner=True)
        executor.resume_approved(resolution.action)
        self.assertEqual(
            [call.args[0].name for call in actions.execute.call_args_list],
            ["battery_status", "whatsapp_message", "screenshot"],
        )

    def test_plan_is_bounded(self):
        executor, actions, _ = self.make_executor(max_steps=2)
        executor.execute_plan(
            [ActionRequest("battery_status") for _ in range(4)],
            is_owner=True,
            source="typed",
        )
        self.assertEqual(actions.execute.call_count, 2)

    def test_system_action_is_terminal(self):
        executor, actions, _ = self.make_executor()
        executor.execute_plan(
            [
                ActionRequest("system_action", {"option": "lock"}),
                ActionRequest("screenshot"),
            ],
            is_owner=True,
            source="typed",
        )
        resolution = executor.confirmations.resolve("confirm", is_owner=True)
        executor.resume_approved(resolution.action)
        self.assertEqual(
            [call.args[0].name for call in actions.execute.call_args_list],
            ["system_action"],
        )


class ActionCatalogTests(unittest.TestCase):
    def test_catalog_and_registry_stay_in_sync(self):
        registry = ActionRegistry(
            AkshSettings(),
            on_reminder=Mock(),
        )
        self.addCleanup(registry.close)
        self.assertEqual(
            set(ACTION_NAMES),
            set(registry.handlers) | set(EXECUTOR_ACTION_NAMES),
        )


if __name__ == "__main__":
    unittest.main()
