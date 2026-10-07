from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    RECEIVED = "received"
    IN_PROGRESS = "in_progress"
    WAITING_CONFIRMATION = "waiting_confirmation"
    WAITING_INPUT = "waiting_input"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class NotebookEvent:
    actor: str
    kind: str
    text: str
    created_at: datetime
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NotebookTask:
    id: str
    title: str
    source: str
    requested_by: str
    assigned_to: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    completed_by: str = ""
    summary: str = ""
    events: list[NotebookEvent] = field(default_factory=list)


OPEN_TASK_STATUSES = {
    TaskStatus.RECEIVED,
    TaskStatus.IN_PROGRESS,
    TaskStatus.WAITING_CONFIRMATION,
    TaskStatus.WAITING_INPUT,
}
