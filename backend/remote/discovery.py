from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections.abc import Callable

import requests

from ..config import AkshSettings


LOGGER = logging.getLogger(__name__)
HEARTBEAT_SECONDS = 6 * 60 * 60


def device_id_for_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]


class DiscoveryPublisher:
    """Publishes the current tunnel URL without storing the pairing token."""

    def __init__(self, settings: AkshSettings, token: str):
        self.settings = settings
        self.token = token
        self.device_id = device_id_for_token(token)
        self._closing = threading.Event()
        self._thread: threading.Thread | None = None
        self._url_provider: Callable[[], str] | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.settings.remote_discovery_url.strip())

    def start(self, url_provider: Callable[[], str]) -> None:
        if not self.enabled or self._thread:
            return
        self._url_provider = url_provider
        self._thread = threading.Thread(
            target=self._run,
            name="aksh-remote-discovery",
            daemon=True,
        )
        self._thread.start()

    def close(self) -> None:
        self._closing.set()

    def publish(self, public_url: str) -> None:
        endpoint = (
            f"{self.settings.remote_discovery_url.rstrip('/')}"
            f"/v1/devices/{self.device_id}"
        )
        response = requests.put(
            endpoint,
            headers={"Authorization": f"Bearer {self.token}"},
            json={"url": public_url},
            timeout=20,
        )
        response.raise_for_status()

    def _run(self) -> None:
        last_url = ""
        last_publish = 0.0
        while not self._closing.is_set():
            public_url = self._url_provider() if self._url_provider else ""
            now = time.monotonic()
            due = now - last_publish >= HEARTBEAT_SECONDS
            if public_url and (public_url != last_url or due):
                try:
                    self.publish(public_url)
                    last_url = public_url
                    last_publish = now
                    LOGGER.info("Phone discovery URL refreshed")
                except requests.RequestException as exc:
                    LOGGER.warning("Phone discovery refresh failed: %s", exc)
                    self._closing.wait(30)
                    continue
            # Check cheaply for a replaced Quick Tunnel URL so phones do not
            # wait minutes after cloudflared recovers from a network change.
            self._closing.wait(5 if not public_url else 10)
