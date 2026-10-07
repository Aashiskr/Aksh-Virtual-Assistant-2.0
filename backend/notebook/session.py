from __future__ import annotations

import threading
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Sequence

from ..models import ActionRequest, ActionResult
from .context import (
    action_value,
    decision_context,
    enrich_actions,
    spoken_summary,
)
from .intents import references_task
from .models import (
    OPEN_TASK_STATUSES,
    NotebookEvent,
    NotebookTask,
    TaskStatus,
)
from .privacy import redact_mapping, redact_text
from .workspace import CurrentWorkspace, WorkspaceWindow


class SessionTaskNotebook:
    """In-memory task history for one Aksh process lifetime only.

    Nothing in this class is written to disk. Closing Aksh clears the notebook,
    and a new launch always starts with an empty session.
    """

    def __init__(
        self, max_tasks: int = 200, workspace: CurrentWorkspace | None = None
    ):
        self.max_tasks = max(20, int(max_tasks))
        self._tasks: deque[NotebookTask] = deque(maxlen=self.max_tasks)
        self.workspace = workspace or CurrentWorkspace()
        self._lock = threading.RLock()

    def start_task(
        self,
        title: str,
        *,
        source: str,
        is_owner: bool,
        assigned_to: str = "aksh",
    ) -> str:
        now = datetime.now().astimezone()
        task = NotebookTask(
            id=uuid.uuid4().hex[:10],
            title=redact_text(title),
            source=redact_text(source, maximum=40),
            requested_by="owner" if is_owner else "friend",
            assigned_to=assigned_to,
            status=TaskStatus.RECEIVED,
            created_at=now,
            updated_at=now,
        )
        task.events.append(
            NotebookEvent(
                actor=task.requested_by,
                kind="request",
                text=task.title,
                created_at=now,
            )
        )
        with self._lock:
            self._tasks.append(task)
        return task.id

    def record_user_event(self, task_id: str | None, text: str, source: str) -> None:
        if not task_id:
            return
        self._append_event(
            task_id,
            actor="user",
            kind="follow_up",
            text=text,
            details={"source": source},
        )

    def record_plan(
        self,
        task_id: str | None,
        actions: Sequence[ActionRequest],
    ) -> None:
        if not task_id:
            return
        details = {"actions": [action_value(action) for action in actions]}
        self._append_event(
            task_id,
            actor="aksh",
            kind="plan",
            text="Aksh planned the requested task.",
            details=details,
            status=TaskStatus.IN_PROGRESS,
        )

    def record_action_started(
        self, task_id: str | None, action: ActionRequest
    ) -> None:
        if not task_id:
            return
        self._append_event(
            task_id,
            actor="aksh",
            kind="action_started",
            text=action.name,
            details=action_value(action),
            status=TaskStatus.IN_PROGRESS,
        )

    def record_action_result(
        self,
        task_id: str | None,
        action: ActionRequest,
        result: ActionResult,
    ) -> None:
        if not task_id:
            return
        self._append_event(
            task_id,
            actor="aksh",
            kind="action_result",
            text=result.message,
            details={
                "success": bool(result.success),
                "action": action_value(action),
            },
            status=(TaskStatus.IN_PROGRESS if result.success else TaskStatus.FAILED),
        )
        self.workspace.record_action(action, result)

    def record_waiting_confirmation(
        self, task_id: str | None, action: ActionRequest, prompt: str
    ) -> None:
        if not task_id:
            return
        self._append_event(
            task_id,
            actor="aksh",
            kind="confirmation_requested",
            text=prompt,
            details={"action": action_value(action)},
            status=TaskStatus.WAITING_CONFIRMATION,
        )

    def record_answer(
        self,
        task_id: str | None,
        answer: str,
        *,
        needs_input: bool = False,
    ) -> None:
        if not task_id:
            return
        self._append_event(
            task_id,
            actor="aksh",
            kind="answer",
            text=answer,
            status=(TaskStatus.WAITING_INPUT if needs_input else TaskStatus.COMPLETED),
        )
        if not needs_input:
            self.finish(task_id, TaskStatus.COMPLETED, answer, completed_by="aksh")

    def finish(
        self,
        task_id: str | None,
        status: TaskStatus,
        summary: str,
        *,
        completed_by: str = "aksh",
    ) -> None:
        if not task_id:
            return
        now = datetime.now().astimezone()
        with self._lock:
            task = self._find(task_id)
            if task is None:
                return
            task.status = status
            task.updated_at = now
            task.summary = redact_text(summary)
            if status == TaskStatus.COMPLETED:
                task.completed_by = completed_by

    def mark_latest_completed_by_user(
        self,
        note: str,
        *,
        source: str,
        is_owner: bool,
    ) -> tuple[str, str]:
        with self._lock:
            task = next(
                (item for item in reversed(self._tasks) if item.status in OPEN_TASK_STATUSES),
                None,
            )
        if task is not None and not references_task(note, task.title):
            task = None
        if task is None:
            task_id = self.start_task(
                note,
                source=source,
                is_owner=is_owner,
                assigned_to="user",
            )
            title = redact_text(note)
        else:
            task_id = task.id
            title = task.title
            self.record_user_event(task_id, note, source)
        self.finish(
            task_id,
            TaskStatus.COMPLETED,
            note,
            completed_by="user",
        )
        return task_id, title

    def enrich_actions(
        self,
        command: str,
        actions: Sequence[ActionRequest],
    ) -> list[ActionRequest]:
        """Fill safe session context that the model omitted.

        A YouTube follow-up inherits the last successful named browser. This is
        what keeps "play Hanuman Chalisa" in Brave after the previous song was
        explicitly played there.
        """
        del command
        with self._lock:
            enriched = enrich_actions(list(self._tasks), actions)
        return self.workspace.enrich_actions(enriched)

    def refresh_workspace(self) -> list[WorkspaceWindow]:
        return self.workspace.refresh()

    def decision_context(self, maximum_characters: int = 5000) -> str:
        with self._lock:
            tasks = decision_context(list(self._tasks), maximum_characters)
        workspace = self.workspace.decision_context()
        return (
            f"Current workspace:\n{workspace}\n\nSession tasks:\n{tasks}"
        )[:maximum_characters]

    def spoken_summary(self) -> str:
        with self._lock:
            tasks = list(self._tasks)
        workspace = self.workspace.spoken_summary()
        if not tasks:
            return (
                "Is session mein abhi Aksh command task record nahi hua. "
                + workspace
            )
        return spoken_summary(tasks) + " " + workspace

    def snapshot(self) -> list[NotebookTask]:
        with self._lock:
            return list(self._tasks)

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()
        self.workspace.clear()

    def _append_event(
        self,
        task_id: str,
        *,
        actor: str,
        kind: str,
        text: str,
        details: dict[str, Any] | None = None,
        status: TaskStatus | None = None,
    ) -> None:
        now = datetime.now().astimezone()
        with self._lock:
            task = self._find(task_id)
            if task is None:
                return
            task.events.append(
                NotebookEvent(
                    actor=actor,
                    kind=kind,
                    text=redact_text(text),
                    created_at=now,
                    details=redact_mapping(details or {}),
                )
            )
            task.updated_at = now
            if status is not None:
                task.status = status

    def _find(self, task_id: str) -> NotebookTask | None:
        return next((task for task in self._tasks if task.id == task_id), None)
