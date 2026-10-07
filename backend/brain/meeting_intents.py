from __future__ import annotations

import re

from ..models import ActionRequest, BrainResponse


def meeting_intent(text: str) -> BrainResponse | None:
    if not re.search(r"\b(?:meeting|meet)\b", text):
        return None
    if not re.search(
        r"\b(?:schedule|scheduled|create|book|set|banao|bana do|bnado|"
        r"lagao|rakh do|rakho)\b",
        text,
    ):
        return None

    account = _account_name(text)
    when = _meeting_time(text)
    if not when:
        return BrainResponse(
            "Meeting kis date aur time par schedule karni hai?",
            needs_clarification=True,
        )

    parameters: dict[str, object] = {"time": when}
    if account:
        parameters["account"] = account
    duration = re.search(
        r"\b(?:for|duration)\s+(\d+(?:\.\d+)?)\s*"
        r"(hours?|hrs?|minutes?|mins?)\b",
        text,
    )
    if duration:
        parameters["duration"] = f"{duration.group(1)} {duration.group(2)}"
    title = re.search(
        r"\b(?:title|subject|named)\s+(?P<title>.+?)"
        r"(?=\s+(?:at|on|for|using|from)\b|$)",
        text,
    )
    if title:
        parameters["title"] = title.group("title").strip()
    emails = re.findall(
        r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}",
        text,
        re.IGNORECASE,
    )
    if account and "@" in account:
        emails = [email for email in emails if email.casefold() != account.casefold()]
    if emails:
        parameters["attendees"] = ", ".join(dict.fromkeys(emails))
    return BrainResponse(actions=[ActionRequest("schedule_meeting", parameters)])


def _account_name(text: str) -> str:
    patterns = (
        r"\b(?:from|using|with)\s+(?P<account>[a-z0-9@._+-]+(?:\s+"
        r"[a-z0-9@._+-]+)*?)\s+account\b",
        r"\b(?P<account>[a-z0-9@._+-]+(?:\s+[a-z0-9@._+-]+)*?)\s+"
        r"account\s+(?:se|sey|from|using)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group("account").strip()
    return ""


def _meeting_time(text: str) -> str:
    iso_time = re.search(r"\b\d{4}-\d{2}-\d{2}[ t]\d{1,2}:\d{2}\b", text)
    if iso_time:
        return iso_time.group(0).replace("t", " ")
    natural_time = re.search(
        r"\b(?:(?P<day>tomorrow|kal)\s+)?(?:at|for|ko|par|pe)?\s*"
        r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*"
        r"(?P<period>am|pm|a\.m\.|p\.m\.|baje)\b",
        text,
    )
    if not natural_time:
        return ""
    pieces = [natural_time.group("day") or "", natural_time.group("hour")]
    if natural_time.group("minute"):
        pieces[-1] += f":{natural_time.group('minute')}"
    period = natural_time.group("period").replace(".", "")
    if period != "baje":
        pieces.append(period)
    return " ".join(filter(None, pieces))
