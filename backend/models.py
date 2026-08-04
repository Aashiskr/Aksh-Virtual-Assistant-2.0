from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Sensitivity(str, Enum):
    SAFE = "safe"
    SENSITIVE = "sensitive"
    DANGEROUS = "dangerous"


@dataclass(slots=True)
class ActionRequest:
    name: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BrainResponse:
    spoken_reply: str = ""
    needs_clarification: bool = False
    actions: list[ActionRequest] = field(default_factory=list)
    used_groq: bool = False


@dataclass(slots=True)
class ActionResult:
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VoiceCapture:
    text: str
    audio: Any
    is_owner: bool = False
    verification_score: float = 0.0
