import unittest

from backend.models import ActionRequest, ActionResult
from backend.notebook import CurrentWorkspace, SessionTaskNotebook, WorkspaceWindow
from backend.notebook.workspace import sanitize_url


class CurrentWorkspaceTests(unittest.TestCase):
    def test_visible_apps_and_browser_page_are_reported(self):
        workspace = CurrentWorkspace()
        workspace.refresh(
            lambda: [
                WorkspaceWindow(
                    "Brave",
                    "Hanuman Chalisa - YouTube",
                    foreground=True,
                    safe_url="https://www.youtube.com/watch",
                ),
                WorkspaceWindow("Chrome", "ChatGPT"),
                WorkspaceWindow("File Explorer", "Downloads"),
            ]
        )

        spoken = workspace.spoken_summary()
        context = workspace.decision_context()
        self.assertIn("Brave", spoken)
        self.assertIn("Hanuman Chalisa", spoken)
        self.assertIn("youtube.com", context)
        self.assertIn("File Explorer", context)

    def test_open_app_is_changed_to_switch_window(self):
        workspace = CurrentWorkspace()
        workspace.refresh(lambda: [WorkspaceWindow("Brave", "YouTube")])
        actions = workspace.enrich_actions(
            [ActionRequest("open_app", {"target": "brave"})]
        )
        self.assertEqual(actions[0].name, "switch_window")
        self.assertEqual(actions[0].parameters["target"], "brave")

    def test_aksh_browser_activity_is_kept_in_session_context(self):
        workspace = CurrentWorkspace()
        workspace.record_action(
            ActionRequest(
                "youtube_play",
                {"query": "Hanuman Chalisa", "target": "brave"},
            ),
            ActionResult(True, "Brave mein Hanuman Chalisa play ho raha hai."),
        )
        context = workspace.decision_context()
        self.assertIn("Recent Aksh browser activity", context)
        self.assertIn("Brave", context)
        self.assertIn("youtube_play", context)

    def test_url_query_and_fragment_are_not_kept(self):
        safe = sanitize_url(
            "https://example.com/private/page?token=secret-value#account"
        )
        self.assertEqual(safe, "https://example.com/private/page")

    def test_clear_removes_apps_and_activity(self):
        workspace = CurrentWorkspace()
        workspace.refresh(lambda: [WorkspaceWindow("Brave", "YouTube")])
        workspace.record_action(
            ActionRequest("open_app", {"target": "brave"}),
            ActionResult(True, "Opened"),
        )
        workspace.clear()
        self.assertEqual(workspace.windows(), [])
        self.assertIn("No supported", workspace.decision_context())


class NotebookWorkspaceIntegrationTests(unittest.TestCase):
    def test_summary_is_not_empty_when_apps_were_open_before_aksh(self):
        workspace = CurrentWorkspace()
        workspace.refresh(
            lambda: [
                WorkspaceWindow("Brave", "Hindi Songs - YouTube"),
                WorkspaceWindow("Chrome", "ChatGPT"),
            ]
        )
        notebook = SessionTaskNotebook(workspace=workspace)
        summary = notebook.spoken_summary()
        self.assertIn("command task record nahi hua", summary)
        self.assertIn("Brave", summary)
        self.assertIn("Hindi Songs", summary)

    def test_workspace_is_available_to_groq_decision_context(self):
        workspace = CurrentWorkspace()
        workspace.refresh(lambda: [WorkspaceWindow("Brave", "YouTube")])
        notebook = SessionTaskNotebook(workspace=workspace)
        context = notebook.decision_context()
        self.assertIn("Current workspace", context)
        self.assertIn("Brave", context)
        self.assertIn("YouTube", context)


if __name__ == "__main__":
    unittest.main()
