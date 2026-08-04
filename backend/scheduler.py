from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable


LOGGER = logging.getLogger(__name__)


def parse_when(value: str, now: datetime | None = None) -> datetime:
    now = now or datetime.now().astimezone()
    raw = " ".join(value.strip().replace(".", "").split())
    if not raw:
        raise ValueError("Time is required")

    try:
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=now.tzinfo)
        return parsed
    except ValueError:
        pass

    match = re.search(
        r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<period>am|pm)?",
        raw,
        re.IGNORECASE,
    )
    if not match:
        raise ValueError(f"I could not understand the time '{value}'")
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    period = (match.group("period") or "").lower()
    if minute > 59:
        raise ValueError("Minutes must be between 00 and 59")
    if period:
        if hour < 1 or hour > 12:
            raise ValueError("12-hour time must use hours 1 to 12")
        hour = hour % 12 + (12 if period == "pm" else 0)
    elif hour > 23:
        raise ValueError("Hour must be between 0 and 23")

    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    lower = raw.lower()
    if "tomorrow" in lower or "kal" in lower:
        candidate += timedelta(days=1)
    elif candidate <= now:
        candidate += timedelta(days=1)
    return candidate


class ReminderScheduler:
    def __init__(
        self,
        path: Path,
        on_due: Callable[[dict[str, Any]], None],
    ):
        self.path = path
        self.on_due = on_due
        self._lock = threading.RLock()
        self._items = self._load()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run, name="aksh-reminders", daemon=True
        )
        self._thread.start()

    def close(self) -> None:
        self._stop.set()

    def add(self, *, kind: str, when: str, message: str) -> dict[str, Any]:
        scheduled_for = parse_when(when)
        item = {
            "id": uuid.uuid4().hex,
            "kind": kind,
            "message": message,
            "scheduled_for": scheduled_for.isoformat(timespec="minutes"),
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "fired": False,
        }
        with self._lock:
            self._items.append(item)
            self._save()
        return item

    def pending(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._items if not item.get("fired")]

    def _run(self) -> None:
        while not self._stop.wait(1.0):
            now = datetime.now().astimezone()
            due: list[dict[str, Any]] = []
            with self._lock:
                for item in self._items:
                    if item.get("fired"):
                        continue
                    try:
                        scheduled = datetime.fromisoformat(item["scheduled_for"])
                    except (KeyError, ValueError):
                        item["fired"] = True
                        continue
                    if scheduled <= now:
                        item["fired"] = True
                        due.append(dict(item))
                if due:
                    self._save()
            for item in due:
                try:
                    self.on_due(item)
                except Exception as exc:
                    LOGGER.warning("Reminder callback failed: %s", exc)

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._items, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        temporary.replace(self.path)
