from __future__ import annotations

from typing import Any

from ..config import AkshSettings


class ActionGroup:
    def __init__(self, settings: AkshSettings):
        self.settings = settings

    @staticmethod
    def required(parameters: dict[str, Any], key: str) -> str:
        value = str(parameters.get(key, "")).strip()
        if not value:
            raise ValueError(f"{key} is required")
        return value
