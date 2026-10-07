from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .pdf_report import NotebookPdfReport

if TYPE_CHECKING:
    from .session import SessionTaskNotebook


@dataclass(frozen=True, slots=True)
class NotebookExportResult:
    path: Path
    format: str
    message: str


class TaskNotebookExporter:
    """Creates and opens an ephemeral PDF, with plain-text fallback."""

    def __init__(self, notebook: SessionTaskNotebook, directory: Path):
        self.notebook = notebook
        self.directory = directory.resolve()

    def export_and_open(self) -> NotebookExportResult:
        result = self.create()
        self._open(result.path)
        return result

    def create(self) -> NotebookExportResult:
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        pdf_path = self.directory / f"aksh-session-task-notebook-{stamp}.pdf"
        try:
            self._create_pdf(pdf_path)
            return NotebookExportResult(
                pdf_path,
                "pdf",
                "Session Task Notebook PDF open kar di hai.",
            )
        except Exception:
            text_path = pdf_path.with_suffix(".txt")
            self._create_text(text_path)
            return NotebookExportResult(
                text_path,
                "text",
                "PDF create nahi hui, isliye Task Notebook text file open ki hai.",
            )

    def close(self) -> None:
        if not self.directory.is_dir():
            return
        for path in self.directory.glob("aksh-session-task-notebook-*"):
            if path.is_file() and path.suffix.casefold() in {".pdf", ".txt", ".tmp"}:
                try:
                    path.unlink()
                except OSError:
                    pass
        try:
            self.directory.rmdir()
        except OSError:
            pass

    def _create_pdf(self, path: Path) -> None:
        NotebookPdfReport(self.notebook).create(path)

    def _create_text(self, path: Path) -> None:
        lines = [
            "AKSH SESSION TASK NOTEBOOK",
            "Automatically deleted when Aksh exits",
            "",
            self.notebook.decision_context(maximum_characters=50000),
            "",
            "FULL TASK EVENTS",
        ]
        for task in self.notebook.snapshot():
            lines.append(f"\n[{task.status.value}] {task.title}")
            for event in task.events:
                lines.append(
                    f"  {event.created_at:%H:%M:%S} {event.actor} "
                    f"{event.kind}: {event.text}"
                )
        path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _open(path: Path) -> None:
        if os.name == "nt":
            os.startfile(str(path))
            return
        command = ["open", str(path)] if os.name == "posix" and Path("/Applications").exists() else ["xdg-open", str(path)]
        subprocess.Popen(command)
