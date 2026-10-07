from __future__ import annotations

import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class RemoteJob:
    id: str
    state: str = "queued"
    heard: str = ""
    report: str = ""
    error: str = ""
    created_at: float = 0.0
    meeting: dict[str, Any] | None = field(default=None)

    def public(self) -> dict[str, object]:
        return asdict(self)


class RemoteJobStore:
    def __init__(self, limit: int = 100):
        self.limit = limit
        self._jobs: dict[str, RemoteJob] = {}
        self._lock = threading.RLock()

    def create(self) -> RemoteJob:
        job = RemoteJob(id=uuid.uuid4().hex, created_at=time.time())
        with self._lock:
            self._jobs[job.id] = job
            self._trim()
        return job

    def get(self, job_id: str) -> RemoteJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def processing(self, job_id: str, heard: str = "") -> None:
        self._update(job_id, state="processing", heard=heard)

    def complete(
        self,
        job_id: str,
        heard: str,
        report: str,
        *,
        meeting: dict[str, Any] | None = None,
    ) -> None:
        self._update(
            job_id,
            state="completed",
            heard=heard,
            report=report,
            error="",
            meeting=meeting,
        )

    def fail(self, job_id: str, error: str, heard: str = "") -> None:
        self._update(
            job_id,
            state="failed",
            heard=heard,
            error=error,
        )

    def _update(self, job_id: str, **values: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for key, value in values.items():
                setattr(job, key, value)

    def _trim(self) -> None:
        overflow = len(self._jobs) - self.limit
        if overflow <= 0:
            return
        oldest = sorted(
            self._jobs.values(), key=lambda job: job.created_at
        )[:overflow]
        for job in oldest:
            self._jobs.pop(job.id, None)
