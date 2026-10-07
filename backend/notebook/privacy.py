from __future__ import annotations

import re
from typing import Any


_SECRET_PATTERNS = (
    re.compile(r"\bgsk_[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b(?:sk|pk)_[A-Za-z0-9_-]{16,}\b"),
    re.compile(
        r"(?i)\b(password|passwd|api[ _-]?key|access[ _-]?token|"
        r"pairing[ _-]?token)\b\s*[:=]?\s*([^\s,;]+)"
    ),
)


def redact_text(value: object, maximum: int = 600) -> str:
    """Keep session context useful without echoing credentials into prompts."""
    text = " ".join(str(value or "").split())
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:
            text = pattern.sub(lambda match: f"{match.group(1)} [REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    return text[:maximum]


def redact_mapping(value: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, item in value.items():
        lowered = str(key).casefold()
        if any(word in lowered for word in ("password", "secret", "token", "api_key")):
            redacted[str(key)] = "[REDACTED]"
        elif isinstance(item, dict):
            redacted[str(key)] = redact_mapping(item)
        elif isinstance(item, (list, tuple)):
            redacted[str(key)] = [
                redact_mapping(entry)
                if isinstance(entry, dict)
                else redact_text(entry, maximum=240)
                if isinstance(entry, str)
                else entry
                for entry in item
            ]
        elif isinstance(item, str):
            redacted[str(key)] = redact_text(item, maximum=240)
        elif isinstance(item, (int, float, bool)) or item is None:
            redacted[str(key)] = item
        else:
            redacted[str(key)] = redact_text(item, maximum=240)
    return redacted
