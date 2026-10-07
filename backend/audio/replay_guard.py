from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from pathlib import Path
from typing import Callable


STARTUP_GRACE_SECONDS = 60.0
STARTUP_HISTORY_WINDOW_SECONDS = 10 * 60.0
CONTINUOUS_DUPLICATE_SECONDS = 90.0
EXPLICIT_WAKE_DUPLICATE_SECONDS = 8.0
HISTORY_TTL_SECONDS = 48 * 60 * 60.0
MAX_HISTORY_ITEMS = 128


class VoiceReplayGuard:
    """Blocks boot-time audio backlog and repeated always-listening commands."""

    def __init__(
        self,
        path: Path,
        *,
        wall_clock: Callable[[], float] = time.time,
        uptime_clock: Callable[[], float] = time.monotonic,
        startup_grace_seconds: float = STARTUP_GRACE_SECONDS,
        startup_history_seconds: float = STARTUP_HISTORY_WINDOW_SECONDS,
        continuous_duplicate_seconds: float = CONTINUOUS_DUPLICATE_SECONDS,
        explicit_duplicate_seconds: float = EXPLICIT_WAKE_DUPLICATE_SECONDS,
        history_ttl_seconds: float = HISTORY_TTL_SECONDS,
    ):
        self.path = path
        self.wall_clock = wall_clock
        self.uptime_clock = uptime_clock
        self.startup_grace_seconds = max(0.0, startup_grace_seconds)
        self.startup_history_seconds = max(0.0, startup_history_seconds)
        self.continuous_duplicate_seconds = max(
            0.0, continuous_duplicate_seconds
        )
        self.explicit_duplicate_seconds = max(0.0, explicit_duplicate_seconds)
        self.history_ttl_seconds = max(60.0, history_ttl_seconds)
        self._started_at = self.uptime_clock()
        self._history = self._load()
        self._recent: dict[str, float] = {}
        self._startup_blocked: set[str] = set()
        self._continuous_session_armed = False
        self._lock = threading.RLock()

    @property
    def continuous_session_armed(self) -> bool:
        with self._lock:
            return self._continuous_session_armed

    def arm_continuous_session(self) -> None:
        """Allow no-wake-word commands after an explicit user activation."""
        with self._lock:
            self._continuous_session_armed = True

    def disarm_continuous_session(self) -> None:
        """Require a fresh activation before accepting continuous speech."""
        with self._lock:
            self._continuous_session_armed = False

    def allow(self, text: str, *, explicit_wake: bool) -> tuple[bool, str]:
        normalized = self._normalize(text)
        if not normalized:
            return False, "empty"
        fingerprint = self._fingerprint(normalized)
        now_wall = self.wall_clock()
        now_uptime = self.uptime_clock()
        uptime = max(0.0, now_uptime - self._started_at)

        with self._lock:
            if explicit_wake:
                self._continuous_session_armed = True
            elif not self._continuous_session_armed:
                return False, "session_not_armed"
            self._prune(now_wall, now_uptime)
            if not explicit_wake and uptime < self.startup_grace_seconds:
                self._startup_blocked.add(fingerprint)
                return False, "startup_grace"
            if not explicit_wake and fingerprint in self._startup_blocked:
                return False, "startup_replay"
            if (
                not explicit_wake
                and uptime < self.startup_history_seconds
                and fingerprint in self._history
            ):
                return False, "previous_session_replay"

            previous = self._recent.get(fingerprint)
            duplicate_window = (
                self.explicit_duplicate_seconds
                if explicit_wake
                else self.continuous_duplicate_seconds
            )
            if previous is not None and now_uptime - previous < duplicate_window:
                return False, "duplicate"

            self._recent[fingerprint] = now_uptime
            self._history[fingerprint] = now_wall
            self._save()
            return True, "accepted"

    @staticmethod
    def _normalize(text: str) -> str:
        value = re.sub(r"[^\w\s]", " ", str(text).casefold(), flags=re.UNICODE)
        return " ".join(value.split())

    @staticmethod
    def _fingerprint(normalized: str) -> str:
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _prune(self, now_wall: float, now_uptime: float) -> None:
        self._history = {
            fingerprint: timestamp
            for fingerprint, timestamp in self._history.items()
            if 0.0 <= now_wall - timestamp <= self.history_ttl_seconds
        }
        maximum_window = max(
            self.continuous_duplicate_seconds,
            self.explicit_duplicate_seconds,
        )
        self._recent = {
            fingerprint: timestamp
            for fingerprint, timestamp in self._recent.items()
            if now_uptime - timestamp <= maximum_window
        }

    def _load(self) -> dict[str, float]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        history = payload.get("history", {}) if isinstance(payload, dict) else {}
        if not isinstance(history, dict):
            return {}
        return {
            str(fingerprint): float(timestamp)
            for fingerprint, timestamp in history.items()
            if isinstance(fingerprint, str)
            and isinstance(timestamp, (int, float))
        }

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        newest = sorted(
            self._history.items(), key=lambda item: item[1], reverse=True
        )[:MAX_HISTORY_ITEMS]
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"history": dict(newest)}, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)
