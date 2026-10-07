from __future__ import annotations

import re


_SUMMARY_PATTERNS = (
    r"\b(?:show|open|read)\s+(?:the\s+)?(?:task\s+)?notebook\b",
    r"\b(?:task\s+)?(?:history|notebook)\s+(?:dikhao|batao|padho)\b",
    r"\b(?:pending|completed|complete)\s+tasks?\s+(?:dikhao|batao|show)\b",
    r"\b(?:what|kya)\s+.*(?:tasks?|kaam).*(?:done|kiya|hua)\b",
    r"\b(?:maine|humne).*(?:aur|and).*(?:aksh|tumne).*(?:kya|what)\b",
)

_USER_COMPLETION_PATTERNS = (
    r"^\s*(?:i\s+(?:have\s+)?done\s+(?:it|this|that)|done\s+by\s+me)\s*[.!]?\s*$",
    r"^\s*(?:maine|main\s+ne)\s+(?:(?:ye|yah|this|that|task|kaam)\s+)?"
    r"(?:kar|complete)\s+(?:diya|liya|kar\s+liya)\s*[.!]?\s*$",
    r"^\s*(?:(?:ye|yah|this|that|task|kaam)\s+)?(?:maine\s+)?"
    r"(?:kar\s+diya|kar\s+liya|complete\s+kar\s+diya)\s*[.!]?\s*$",
    r"^\s*(?:task|kaam)\s+(?:ho\s+gaya|done|completed),?\s*(?:maine)?\s*[.!]?\s*$",
    r"^\s*(?:maine|main\s+ne)\s+.+\s+"
    r"(?:kar\s+diya|kar\s+liya|complete\s+kar\s+diya|completed|done)\s*[.!]?\s*$",
)


def is_summary_request(text: str) -> bool:
    normalized = " ".join(str(text or "").casefold().split())
    return any(re.search(pattern, normalized) for pattern in _SUMMARY_PATTERNS)


def is_user_completion_report(text: str) -> bool:
    normalized = " ".join(str(text or "").casefold().split())
    return any(re.search(pattern, normalized) for pattern in _USER_COMPLETION_PATTERNS)


def references_task(note: str, title: str) -> bool:
    generic = {
        "i",
        "it",
        "this",
        "that",
        "done",
        "task",
        "kaam",
        "kar",
        "diya",
        "liya",
        "complete",
        "completed",
        "maine",
        "main",
        "ne",
        "ye",
        "yah",
    }
    note_words = set(re.findall(r"[a-z0-9]+", note.casefold())) - generic
    if not note_words:
        return True
    title_words = set(re.findall(r"[a-z0-9]+", title.casefold())) - generic
    return bool(note_words & title_words)
