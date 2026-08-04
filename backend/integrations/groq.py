from __future__ import annotations

from typing import Any

import requests

from ..config import AkshSettings


class GroqClient:
    """Shared authenticated transport for Groq chat and audio APIs."""

    def __init__(self, settings: AkshSettings):
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self.settings.groq_api_key)

    def post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
        files: dict[str, Any] | None = None,
        timeout: float = 30,
    ) -> requests.Response:
        if not self.enabled:
            raise RuntimeError("Groq API key configured nahi hai.")
        headers = {"Authorization": f"Bearer {self.settings.groq_api_key}"}
        if json is not None:
            headers["Content-Type"] = "application/json"
        return requests.post(
            f"{self.settings.groq_base_url.rstrip('/')}/{path.lstrip('/')}",
            headers=headers,
            json=json,
            data=data,
            files=files,
            timeout=timeout,
        )
