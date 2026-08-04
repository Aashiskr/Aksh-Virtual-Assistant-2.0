from __future__ import annotations

import re
from collections.abc import Iterable


DEFAULT_WAKE_ALIASES = (
    "x",
    "ex",
    "ax",
    "aksh",
    "akash",
    "aakash",
    "hey akash",
    "hey aakash",
    "एक",
    "आकाश",
    "अक्ष",
)


def match_wake(
    text: str,
    phrases: Iterable[str],
    aliases: Iterable[str] = DEFAULT_WAKE_ALIASES,
) -> tuple[bool, str]:
    """Returns whether a wake phrase was heard and any command after it."""
    normalized = " ".join(text.strip().split())
    lowered = normalized.lower()
    candidates = sorted(
        {phrase.lower().strip() for phrase in (*phrases, *aliases) if phrase.strip()},
        key=len,
        reverse=True,
    )
    for candidate in candidates:
        pattern = rf"^(?:hey\s+)?{re.escape(candidate)}(?:\b|[\s,!.?-])"
        match = re.match(pattern, lowered, flags=re.IGNORECASE)
        if match:
            command = normalized[match.end() :].strip(" ,.!?-")
            return True, command
    return False, ""
