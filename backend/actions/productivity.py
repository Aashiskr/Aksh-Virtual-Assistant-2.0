from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ..capabilities.ocr import extract_text, parse_identity_fields
from ..capabilities.tutor import coach_english
from ..models import ActionResult
from ..scheduler import ReminderScheduler
from .base import ActionGroup


class ProductivityActions(ActionGroup):
    def __init__(self, settings, on_reminder):
        super().__init__(settings)
        self.scheduler = ReminderScheduler(
            settings.data_dir / "schedules.json", on_due=on_reminder
        )

    def start(self) -> None:
        self.scheduler.start()

    def close(self) -> None:
        self.scheduler.close()

    def set_reminder(self, parameters: dict[str, Any]) -> ActionResult:
        item = self.scheduler.add(
            kind="reminder",
            when=self.required(parameters, "time"),
            message=self.required(parameters, "message"),
        )
        return ActionResult(True, self._scheduled_message("Reminder", item))

    def set_alarm(self, parameters: dict[str, Any]) -> ActionResult:
        item = self.scheduler.add(
            kind="alarm",
            when=self.required(parameters, "time"),
            message="Alarm",
        )
        return ActionResult(True, self._scheduled_message("Alarm", item))

    def english_tutor(self, parameters: dict[str, Any]) -> ActionResult:
        sentence = str(parameters.get("query") or "")
        return ActionResult(True, coach_english(self.settings, sentence))

    def fill_form(self, parameters: dict[str, Any]) -> ActionResult:
        target = self.required(parameters, "target")
        path = Path(target).expanduser()
        if not path.is_absolute():
            path = self.settings.project_root / path
        text = extract_text(path)
        if not text:
            return ActionResult(False, f"{target} read nahi ho paaya.")
        fields = parse_identity_fields(text)
        if not fields:
            return ActionResult(
                False,
                "Image read hui, lekin name, DOB ya phone field nahi mili.",
            )
        preview = ", ".join(f"{key}: {value}" for key, value in fields.items())
        return ActionResult(
            True,
            f"Fields mil gaye: {preview}. Privacy ke liye form submit nahi kiya.",
            {"fields": fields, "source": str(path)},
        )

    @staticmethod
    def _scheduled_message(kind: str, item: dict[str, Any]) -> str:
        shown = datetime.fromisoformat(item["scheduled_for"]).strftime(
            "%d %B, %I:%M %p"
        )
        return f"{kind} {shown} ke liye set ho gaya."
