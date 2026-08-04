from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from .config import AkshSettings
from .models import ActionRequest
from .permissions import action_description
from .security import SecurityManager


@dataclass(slots=True)
class ConfirmationResolution:
    state: str
    message: str
    action: ActionRequest | None = None


@dataclass(slots=True)
class _PendingConfirmation:
    action: ActionRequest
    description: str
    created_at: float
    source: str


class ConfirmationManager:
    """Keeps one protected action pending across laptop and phone commands."""

    def __init__(
        self,
        settings: AkshSettings,
        security: SecurityManager,
        status: Callable[[str, str], None],
        message: Callable[[str, str], None],
        *,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.settings = settings
        self.security = security
        self.status = status
        self.message = message
        self.clock = clock
        self._pending: _PendingConfirmation | None = None
        self._lock = threading.RLock()

    @property
    def pending_action(self) -> ActionRequest | None:
        with self._lock:
            return self._pending.action if self._pending else None

    def request(self, action: ActionRequest, *, source: str) -> str:
        description = action_description(action)
        with self._lock:
            self._pending = _PendingConfirmation(
                action=action,
                description=description,
                created_at=self.clock(),
                source=source,
            )
        prompt = (
            f"{description} ke liye confirmation chahiye. "
            "Phone ya laptop se confirm boliye, ya cancel boliye."
        )
        self.status("permission", f"Confirmation: {description}")
        self.message("permission", prompt)
        return prompt

    def resolve(
        self, text: str, *, is_owner: bool
    ) -> ConfirmationResolution | None:
        negative = self.security.is_negative(text)
        # Execution approval is intentionally stricter than conversational
        # affirmation. The entire utterance must be a confirmation so a
        # corrected command cannot accidentally approve an older request.
        affirmative = self.security.is_confirmation_only(text)
        with self._lock:
            pending = self._pending
            if not pending:
                if affirmative or negative:
                    return ConfirmationResolution(
                        "missing", "Koi confirmation pending nahi hai."
                    )
                return None
            if self._expired(pending):
                self._pending = None
                if affirmative or negative:
                    return ConfirmationResolution(
                        "expired",
                        "Confirmation expire ho gayi. Command dobara boliye.",
                    )
                return None
            if negative:
                self._pending = None
                message = f"{pending.description} cancel kar diya."
                self.message("permission", message)
                return ConfirmationResolution("denied", message)
            if affirmative:
                if not is_owner:
                    message = (
                        "Ye confirmation owner se chahiye. Pending request "
                        "abhi active hai."
                    )
                    self.message("permission", message)
                    return ConfirmationResolution("unauthorized", message)
                self._pending = None
                self.message("permission", "Owner confirmed")
                return ConfirmationResolution(
                    "approved",
                    f"{pending.description} confirmed.",
                    pending.action,
                )
            return ConfirmationResolution(
                "waiting",
                f"{pending.description} pending hai. Confirm ya cancel boliye.",
            )

    def _expired(self, pending: _PendingConfirmation) -> bool:
        return (
            self.clock() - pending.created_at
            >= self.settings.confirmation_timeout_seconds
        )
