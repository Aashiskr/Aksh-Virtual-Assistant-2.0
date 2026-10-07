from __future__ import annotations

import secrets
import threading
import time
from collections import deque
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
        on_expire: Callable[[list[ScreenSession]], None] | None = None,
    ):
        self.ttl_seconds = max(60.0, float(ttl_seconds))
        self.maximum_sessions = max(1, int(maximum_sessions))
        self.clock = clock
        self.on_expire = on_expire
        self._sessions: dict[str, ScreenSession] = {}
        self._revoked: deque[str] = deque(maxlen=64)
        self._lock = threading.RLock()

    def create(self) -> ScreenSession:
        with self._lock:
            expired = self._remove_expired_locked()
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
        self._notify_expired(expired)
        return session

    def require(self, token: str) -> ScreenSession:
        normalized = str(token)
        with self._lock:
            expired = self._remove_expired_locked()
            session = self._sessions.get(normalized)
            revoked = normalized in self._revoked
            if session is not None:
                session.last_seen_at = self.clock()
        self._notify_expired(expired)
        if session is not None:
            return session
        if revoked:
            raise PermissionError(
                "Remote screen session was replaced by a newer connection."
            )
        raise KeyError("Remote screen session expired or invalid.")

    def remove(self, token: str) -> ScreenSession | None:
        with self._lock:
            return self._sessions.pop(str(token), None)

    def attach_peer(self, token: str, peer: object) -> object | None:
        """Attach a WebRTC peer without making peer failure revoke the session."""
        normalized = str(token)
        with self._lock:
            expired = self._remove_expired_locked()
            session = self._sessions.get(normalized)
            revoked = normalized in self._revoked
            if session is not None:
                previous = session.peer
                session.peer = peer
                session.last_seen_at = self.clock()
            else:
                previous = None
        self._notify_expired(expired)
        if session is not None:
            return previous
        if revoked:
            raise PermissionError(
                "Remote screen session was replaced by a newer connection."
            )
        raise KeyError("Remote screen session expired or invalid.")

    def detach_peer(self, token: str, peer: object) -> bool:
        """Detach only the matching peer while keeping HTTPS fallback alive."""
        with self._lock:
            session = self._sessions.get(str(token))
            if session is None or session.peer is not peer:
                return False
            session.peer = None
            return True

    def clear(self, *, remember_revoked: bool = False) -> list[ScreenSession]:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
            if remember_revoked:
                self._revoked.extend(session.token for session in sessions)
            return sessions

    def active_count(self) -> int:
        with self._lock:
            expired = self._remove_expired_locked()
            count = len(self._sessions)
        self._notify_expired(expired)
        return count

    def _remove_expired_locked(self) -> list[ScreenSession]:
        now = self.clock()
        expired = [
            session
            for session in self._sessions.values()
            if now - session.last_seen_at > self.ttl_seconds
        ]
        for session in expired:
            self._sessions.pop(session.token, None)
        return expired

    def _notify_expired(self, expired: list[ScreenSession]) -> None:
        if expired and self.on_expire is not None:
            self.on_expire(expired)
