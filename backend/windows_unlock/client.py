from __future__ import annotations

from collections.abc import Callable
from typing import Any

import requests
from fastapi import Depends, FastAPI, HTTPException


class WindowsUnlockClient:
    def __init__(self, token: str, base_url: str = "http://127.0.0.1:8766"):
        self.token = token
        self.base_url = base_url.rstrip("/")

    def health(self) -> dict[str, Any]:
        try:
            return self._request("GET", "/v1/health")
        except (requests.RequestException, ValueError, HTTPException):
            return {
                "computer_state": "unavailable",
                "unlock_available": False,
                "phone_enrolled": False,
                "boot_id": "",
            }

    def relay(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            return self._request("POST", path, payload)
        except requests.RequestException as exc:
            raise HTTPException(503, "Windows unlock broker is unavailable") from exc

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        response = requests.request(
            method,
            self.base_url + path,
            headers={"Authorization": f"Bearer {self.token}"},
            json=payload,
            timeout=4,
        )
        try:
            value = response.json()
        except ValueError:
            value = {}
        if response.status_code >= 400:
            raise HTTPException(
                response.status_code,
                str(value.get("detail", "Windows unlock request failed")),
            )
        return value


def attach_windows_unlock_routes(
    app: FastAPI,
    client: WindowsUnlockClient,
    authorize: Callable[..., None],
) -> None:
    @app.post("/v1/unlock/enroll")
    def enroll(
        payload: dict[str, Any], _: None = Depends(authorize)
    ) -> dict[str, Any]:
        return client.relay("/v1/unlock/enroll", payload)

    @app.post("/v1/unlock/challenge")
    def challenge(_: None = Depends(authorize)) -> dict[str, Any]:
        return client.relay("/v1/unlock/challenge")

    @app.post("/v1/unlock/approve")
    def approve(
        payload: dict[str, Any], _: None = Depends(authorize)
    ) -> dict[str, Any]:
        return client.relay("/v1/unlock/approve", payload)
