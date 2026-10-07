from __future__ import annotations

from collections.abc import Callable

from .export import TaskNotebookExporter
from .models import TaskStatus
from .session import SessionTaskNotebook


def present_notebook(
    notebook: SessionTaskNotebook,
    exporter: TaskNotebookExporter | None,
    task_id: str | None,
    *,
    status: Callable[[str, str], None],
    message: Callable[[str, str], None],
    say: Callable[[str], None],
) -> str:
    """Open the notebook file silently; speak only for legacy/no-export use."""
    if exporter is None:
        summary = notebook.spoken_summary()
        notebook.record_answer(task_id, summary)
        say(summary)
        return summary
    try:
        result = exporter.export_and_open()
        reply = result.message
        notebook.record_answer(task_id, reply)
        status("working", reply)
        message("aksh", reply)
        return reply
    except Exception as exc:
        reply = f"Task Notebook file create nahi hui: {exc}"
        notebook.finish(task_id, TaskStatus.FAILED, reply)
        status("error", reply)
        message("aksh", reply)
        return reply
