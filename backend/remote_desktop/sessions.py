from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class ScreenSession:
    token: str
    created_at: float
    last_seen_at: float
    peer: object | None = None


class ScreenSessionStore:
    def __init__(
        self,
        *,
        ttl_seconds: float = 30 * 60,
        maximum_sessions: int = 2,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.ttl_seconds = max(60.0, float(ttl_seconds))
        self.maximum_sessions = max(1, int(maximum_sessions))
        self.clock = clock
        self._sessions: dict[str, ScreenSession] = {}
        self._lock = threading.RLock()

    def create(self) -> ScreenSession:
        with self._lock:
            self._remove_expired_locked()
            while len(self._sessions) >= self.maximum_sessions:
                oldest = min(
                    self._sessions.values(),
                    key=lambda item: item.last_seen_at,
                )
                self._sessions.pop(oldest.token, None)
            now = self.clock()
            session = ScreenSession(
                token=secrets.token_urlsafe(32),
                created_at=now,
                last_seen_at=now,
            )
            self._sessions[session.token] = session
            return session

    def require(self, token: str) -> ScreenSession:
        with self._lock:
            self._remove_expired_locked()
            session = self._sessions.get(str(token))
            if session is None:
                raise KeyError("Remote screen session expired or invalid.")
            session.last_seen_at = self.clock()
            return session

    def remove(self, token: str) -> ScreenSession | None:
        with self._lock:
            return self._sessions.pop(str(token), None)

    def clear(self) -> list[ScreenSession]:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
            return sessions

    def active_count(self) -> int:
        with self._lock:
            self._remove_expired_locked()
            return len(self._sessions)

    def _remove_expired_locked(self) -> None:
        now = self.clock()
        expired = [
            token
            for token, session in self._sessions.items()
            if now - session.last_seen_at > self.ttl_seconds
        ]
        for token in expired:
            self._sessions.pop(token, None)
