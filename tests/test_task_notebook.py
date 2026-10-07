import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from backend.command_processor import CommandProcessor
from backend.config import AkshSettings
from backend.confirmations import ConfirmationManager
from backend.models import ActionRequest, ActionResult, BrainResponse
from backend.notebook import SessionTaskNotebook, TaskStatus
from backend.security import SecurityManager


class SessionTaskNotebookTests(unittest.TestCase):
    def test_records_user_request_plan_and_aksh_result(self):
        notebook = SessionTaskNotebook()
        task_id = notebook.start_task(
            "Brave mein Hindi song chalao",
            source="phone",
            is_owner=True,
        )
        action = ActionRequest(
            "youtube_play",
            {"query": "Hindi song", "target": "brave"},
        )
        notebook.record_plan(task_id, [action])
        notebook.record_action_started(task_id, action)
        notebook.record_action_result(
            task_id,
            action,
            ActionResult(True, "Brave mein Hindi song play ho gaya."),
        )
        notebook.finish(
            task_id,
            TaskStatus.COMPLETED,
            "Brave mein Hindi song play ho gaya.",
            completed_by="aksh",
        )

        task = notebook.snapshot()[0]
        self.assertEqual(task.requested_by, "owner")
        self.assertEqual(task.completed_by, "aksh")
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.events[-1].kind, "action_result")

    def test_youtube_follow_up_inherits_successful_session_browser(self):
        notebook = SessionTaskNotebook()
        task_id = notebook.start_task(
            "Brave mein Hindi song chalao",
            source="phone",
            is_owner=True,
        )
        previous = ActionRequest(
            "youtube_play",
            {"query": "Hindi song", "target": "brave"},
        )
        notebook.record_action_result(
            task_id,
            previous,
            ActionResult(True, "Playing"),
        )

        actions = notebook.enrich_actions(
            "ab Hanuman Chalisa chalao",
            [ActionRequest("youtube_play", {"query": "Hanuman Chalisa"})],
        )

        self.assertEqual(actions[0].parameters["target"], "brave")

    def test_failed_browser_action_is_not_reused(self):
        notebook = SessionTaskNotebook()
        task_id = notebook.start_task("song", source="typed", is_owner=True)
        notebook.record_action_result(
            task_id,
            ActionRequest(
                "youtube_play",
                {"query": "song", "target": "brave"},
            ),
            ActionResult(False, "Brave not found"),
        )

        actions = notebook.enrich_actions(
            "another song",
            [ActionRequest("youtube_play", {"query": "another song"})],
        )

        self.assertNotIn("target", actions[0].parameters)

    def test_clear_removes_whole_session(self):
        notebook = SessionTaskNotebook()
        notebook.start_task("open Chrome", source="typed", is_owner=True)
        notebook.clear()
        self.assertEqual(notebook.snapshot(), [])
        self.assertIn("command task record nahi hua", notebook.spoken_summary())

    def test_secret_is_redacted_from_decision_context(self):
        notebook = SessionTaskNotebook()
        notebook.start_task(
            "use gsk_abcdefghijklmnopqrstuvwxyz123456",
            source="typed",
            is_owner=True,
        )
        context = notebook.decision_context()
        self.assertNotIn("gsk_", context)
        self.assertIn("[REDACTED]", context)

    def test_user_can_complete_matching_open_task(self):
        notebook = SessionTaskNotebook()
        task_id = notebook.start_task(
            "CV upload karna",
            source="typed",
            is_owner=True,
            assigned_to="user",
        )
        completed_id, _ = notebook.mark_latest_completed_by_user(
            "maine CV upload kar diya",
            source="typed",
            is_owner=True,
        )
        self.assertEqual(completed_id, task_id)
        self.assertEqual(notebook.snapshot()[0].completed_by, "user")

    def test_unrelated_user_completion_does_not_close_open_aksh_task(self):
        notebook = SessionTaskNotebook()
        notebook.start_task(
            "computer shutdown",
            source="phone",
            is_owner=True,
        )
        notebook.mark_latest_completed_by_user(
            "maine CV upload kar diya",
            source="phone",
            is_owner=True,
        )
        tasks = notebook.snapshot()
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0].status, TaskStatus.RECEIVED)
        self.assertEqual(tasks[1].completed_by, "user")


class NotebookDecisionFlowTests(unittest.TestCase):
    def test_second_youtube_command_stays_in_brave(self):
        settings = AkshSettings()
        security = SecurityManager()
        confirmations = ConfirmationManager(settings, security, Mock(), Mock())
        notebook = SessionTaskNotebook()
        brain = Mock(settings=settings)
        brain.understand.side_effect = [
            BrainResponse(
                actions=[
                    ActionRequest(
                        "youtube_play",
                        {"query": "Hindi song", "target": "brave"},
                    )
                ]
            ),
            BrainResponse(
                actions=[
                    ActionRequest(
                        "youtube_play",
                        {"query": "Hanuman Chalisa"},
                    )
                ]
            ),
        ]
        actions = Mock()
        actions.shopping = SimpleNamespace(followup=lambda text: None)
        actions.web = SimpleNamespace(followup=lambda text: None)
        actions.execute.return_value = ActionResult(True, "Playing")
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
            notebook=notebook,
        )

        processor.process(
            "YouTube par Hindi song Brave mein chalao",
            is_owner=True,
            source="phone",
        )
        processor.process(
            "ab Hanuman Chalisa chalao",
            is_owner=True,
            source="phone",
        )

        second_action = actions.execute.call_args_list[1].args[0]
        self.assertEqual(second_action.parameters["target"], "brave")


if __name__ == "__main__":
    unittest.main()
