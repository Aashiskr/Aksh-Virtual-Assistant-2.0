from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .calendar_browser import ChromeCalendarBrowser, MeetingDraft
from .chrome_accounts import ChromeAccountResolver, MeetingSchedulingError
from .scheduler import parse_when


class MeetingStore:
    def __init__(self, path: Path):
        self.path = path

    def append(self, meeting: dict[str, Any]) -> None:
        meetings = self.all()
        meetings.append(dict(meeting))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(meetings[-200:], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def all(self) -> list[dict[str, Any]]:
        value = _read_json(self.path)
        return [item for item in value if isinstance(item, dict)] if isinstance(
            value, list
        ) else []

    def latest(self) -> dict[str, Any] | None:
        meetings = self.all()
        return dict(meetings[-1]) if meetings else None

    def latest_id(self) -> str:
        latest = self.latest() or {}
        return str(latest.get("id") or "")


class GoogleMeetingScheduler:
    def __init__(
        self,
        settings,
        *,
        resolver: ChromeAccountResolver | None = None,
        browser: ChromeCalendarBrowser | None = None,
    ):
        self.settings = settings
        self.resolver = resolver or ChromeAccountResolver()
        self.store = MeetingStore(settings.data_dir / "meetings.json")
        if browser is None:
            from .actions.browser_detection import find_browser_executable

            executable = find_browser_executable("chrome")
            if executable is None:
                raise MeetingSchedulingError("Google Chrome installed nahi mila.")
            browser = ChromeCalendarBrowser(executable)
        self.browser = browser

    def schedule(self, parameters: dict[str, Any]) -> dict[str, Any]:
        when_label = str(parameters.get("time") or "").strip()
        if not when_label:
            raise MeetingSchedulingError("Meeting ka time required hai.")
        start = parse_when(when_label)
        minutes = _duration_minutes(parameters.get("duration"))
        title = str(parameters.get("title") or "Meeting scheduled by Aksh").strip()
        title = title[:200] or "Meeting scheduled by Aksh"
        attendees = _attendee_emails(parameters.get("attendees"))
        requested_account = str(parameters.get("account") or "").strip()
        account = self.resolver.resolve(requested_account)
        draft = MeetingDraft(
            title=title,
            start=start,
            end=start + timedelta(minutes=minutes),
            attendees=attendees,
        )
        link = self.browser.schedule(account, draft)
        meeting = {
            "id": uuid.uuid4().hex,
            "title": title,
            "time": when_label,
            "scheduled_for": start.isoformat(timespec="minutes"),
            "ends_at": draft.end.isoformat(timespec="minutes"),
            "account": account.label,
            "account_email": account.email,
            "requested_account": requested_account,
            "link": link,
            "attendees": list(attendees),
            "created_at": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
        }
        self.store.append(meeting)
        return meeting


def public_meeting(meeting: dict[str, Any] | None) -> dict[str, Any] | None:
    if not meeting:
        return None
    allowed = (
        "id",
        "title",
        "time",
        "scheduled_for",
        "ends_at",
        "account",
        "account_email",
        "link",
        "attendees",
        "created_at",
    )
    return {key: meeting[key] for key in allowed if key in meeting}


def _duration_minutes(value: Any) -> int:
    if value is None or str(value).strip() == "":
        return 60
    if isinstance(value, (int, float)):
        minutes = int(value)
    else:
        raw = str(value).strip().casefold()
        match = re.search(
            r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?)?", raw
        )
        if not match:
            raise MeetingSchedulingError("Meeting duration samajh nahi aayi.")
        amount = float(match.group(1))
        unit = match.group(2) or "minutes"
        minutes = (
            round(amount * 60)
            if unit.startswith(("hour", "hr"))
            else round(amount)
        )
    if minutes < 5 or minutes > 1440:
        raise MeetingSchedulingError(
            "Meeting duration 5 minutes se 24 hours honi chahiye."
        )
    return minutes


def _attendee_emails(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        raw = " ".join(str(item) for item in value)
    else:
        raw = str(value)
    emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", raw, re.I)
    return tuple(dict.fromkeys(email.casefold() for email in emails))


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
