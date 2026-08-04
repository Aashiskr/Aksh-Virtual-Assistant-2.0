from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MeetingTurn:
    timestamp: str
    source: str
    text: str


@dataclass(slots=True)
class MeetingExchange:
    timestamp: str
    question: str
    suggested_answer: str
    key_points: list[str] = field(default_factory=list)
    owner_reply: str = ""
    correction: str = ""
    better_answer: str = ""


@dataclass(slots=True)
class ReplyReview:
    needs_correction: bool
    correction: str = ""
    better_answer: str = ""
