from __future__ import annotations

from typing import Any, Sequence

from ..models import ActionRequest
from .models import OPEN_TASK_STATUSES, NotebookTask, TaskStatus
from .privacy import redact_mapping


def action_value(action: ActionRequest) -> dict[str, Any]:
    return {
        "name": action.name,
        "parameters": redact_mapping(action.parameters),
    }


def latest_successful_action(
    tasks: Sequence[NotebookTask], name: str
) -> dict[str, Any] | None:
    for task in reversed(tasks):
        for event in reversed(task.events):
            if event.kind != "action_result" or not event.details.get("success"):
                continue
            action = event.details.get("action")
            if isinstance(action, dict) and action.get("name") == name:
                return dict(action)
    return None


def enrich_actions(
    tasks: Sequence[NotebookTask],
    actions: Sequence[ActionRequest],
) -> list[ActionRequest]:
    enriched = [
        ActionRequest(action.name, dict(action.parameters)) for action in actions
    ]
    previous = latest_successful_action(tasks, "youtube_play")
    browser = (
        str(previous.get("parameters", {}).get("target", "")).strip()
        if previous
        else ""
    )
    if not browser:
        return enriched
    for action in enriched:
        if action.name == "youtube_play" and not action.parameters.get("target"):
            action.parameters["target"] = browser
    return enriched


def decision_context(
    tasks: Sequence[NotebookTask], maximum_characters: int = 5000
) -> str:
    if not tasks:
        return "No tasks recorded in this session yet."
    lines: list[str] = []
    for task in tasks[-12:]:
        plan = _last_plan_text(task)
        result = task.summary or _last_result_text(task)
        line = (
            f"- status={task.status.value}; requested_by={task.requested_by}; "
            f"assigned_to={task.assigned_to}; "
            f"completed_by={task.completed_by or '-'}; task={task.title}"
        )
        if plan:
            line += f"; plan={plan}"
        if result:
            line += f"; result={result}"
        lines.append(line)
    return "\n".join(lines)[-maximum_characters:]


def spoken_summary(tasks: Sequence[NotebookTask]) -> str:
    if not tasks:
        return "Is session ka task notebook abhi empty hai."
    open_tasks = [task for task in tasks if task.status in OPEN_TASK_STATUSES]
    completed = [task for task in tasks if task.status == TaskStatus.COMPLETED]
    failed = [task for task in tasks if task.status == TaskStatus.FAILED]
    details = "; ".join(
        f"{task.title} — {task.status.value.replace('_', ' ')}"
        + (f" by {task.completed_by}" if task.completed_by else "")
        for task in tasks[-5:]
    )
    return (
        f"Is session mein {len(tasks)} tasks note hue: {len(open_tasks)} open, "
        f"{len(completed)} completed aur {len(failed)} failed. Recent: {details}."
    )


def _last_plan_text(task: NotebookTask) -> str:
    for event in reversed(task.events):
        if event.kind != "plan":
            continue
        actions = event.details.get("actions", [])
        if isinstance(actions, list):
            return ", ".join(
                str(action.get("name", ""))
                for action in actions
                if isinstance(action, dict)
            )
    return ""


def _last_result_text(task: NotebookTask) -> str:
    for event in reversed(task.events):
        if event.kind in {"action_result", "answer"}:
            return event.text
    return ""
