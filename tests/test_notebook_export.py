import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pypdf import PdfReader

from backend.models import ActionRequest, ActionResult
from backend.notebook import (
    CurrentWorkspace,
    SessionTaskNotebook,
    TaskNotebookExporter,
    WorkspaceWindow,
)
from backend.notebook.presentation import present_notebook


class TaskNotebookExporterTests(unittest.TestCase):
    def make_notebook(self):
        workspace = CurrentWorkspace()
        workspace.refresh(
            lambda: [
                WorkspaceWindow(
                    "Brave",
                    "Hanuman Chalisa - YouTube",
                    foreground=True,
                    safe_url="https://www.youtube.com/watch",
                )
            ]
        )
        notebook = SessionTaskNotebook(workspace=workspace)
        task_id = notebook.start_task(
            "Brave mein Hanuman Chalisa chalao",
            source="phone",
            is_owner=True,
        )
        action = ActionRequest(
            "youtube_play",
            {"query": "Hanuman Chalisa", "target": "brave"},
        )
        notebook.record_plan(task_id, [action])
        notebook.record_action_result(
            task_id,
            action,
            ActionResult(True, "Brave mein Hanuman Chalisa play ho raha hai."),
        )
        return notebook

    def test_pdf_contains_workspace_and_task_details(self):
        with tempfile.TemporaryDirectory() as folder:
            exporter = TaskNotebookExporter(self.make_notebook(), Path(folder))
            result = exporter.create()
            self.assertEqual(result.format, "pdf")
            self.assertTrue(result.path.is_file())
            reader = PdfReader(str(result.path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            self.assertIn("Aksh Session Task Notebook", text)
            self.assertIn("Current Workspace", text)
            self.assertIn("Brave", text)
            self.assertIn("Hanuman Chalisa", text)

    def test_text_fallback_is_used_if_pdf_creation_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            exporter = TaskNotebookExporter(self.make_notebook(), Path(folder))
            with patch.object(exporter, "_create_pdf", side_effect=RuntimeError):
                result = exporter.create()
            self.assertEqual(result.format, "text")
            self.assertIn("CURRENT WORKSPACE", result.path.read_text(encoding="utf-8").upper())

    def test_close_deletes_session_exports(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / "session_notebook"
            exporter = TaskNotebookExporter(self.make_notebook(), directory)
            result = exporter.create()
            exporter.close()
            self.assertFalse(result.path.exists())
            self.assertFalse(directory.exists())


class NotebookPresentationTests(unittest.TestCase):
    def test_file_is_opened_without_speaking_summary(self):
        notebook = SessionTaskNotebook()
        task_id = notebook.start_task("notebook dikhao", source="phone", is_owner=True)
        exporter = Mock()
        exporter.export_and_open.return_value = Mock(
            message="Session Task Notebook PDF open kar di hai."
        )
        say = Mock()
        reply = present_notebook(
            notebook,
            exporter,
            task_id,
            status=Mock(),
            message=Mock(),
            say=say,
        )
        self.assertIn("PDF open", reply)
        say.assert_not_called()


if __name__ == "__main__":
    unittest.main()
