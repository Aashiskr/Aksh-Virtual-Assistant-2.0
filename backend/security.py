from __future__ import annotations

import re
import threading

from .agent.catalog import sensitivity_for
from .models import ActionRequest, Sensitivity


class SecurityManager:
    """Owns speaker authorization and action confirmation policy."""

    _CONFIRMATION_PHRASES = {
        "yes",
        "yes confirm",
        "confirm",
        "confirmed",
        "confirm karo",
        "confirm kar do",
        "conform",
        "yes allow",
        "yes allow it",
        "allow",
        "allow it",
        "allowed",
        "approved",
        "approve",
        "haan",
        "han",
        "haan karo",
        "haan kar do",
        "han kar do",
        "kar do",
        "permission hai",
        "permission granted",
        "i allow",
        "proceed",
        "go ahead",
        "yes do it",
        "ok do it",
        "okay do it",
        "कन्फर्म",
        "कंफर्म",
        "हाँ",
        "हां",
        "कर दो",
    }

    def __init__(self, *, confirm_sensitive_actions: bool = True) -> None:
        self._friends_mode = False
        self.confirm_sensitive_actions = confirm_sensitive_actions
        self._lock = threading.RLock()

    @property
    def friends_mode(self) -> bool:
        with self._lock:
            return self._friends_mode

    def set_friends_mode(self, enabled: bool, *, requested_by_owner: bool) -> bool:
        if not requested_by_owner:
            return False
        with self._lock:
            self._friends_mode = enabled
        return True

    def speaker_is_allowed(self, is_owner: bool) -> bool:
        return is_owner or self.friends_mode

    @staticmethod
    def sensitivity(action: ActionRequest | str) -> Sensitivity:
        return sensitivity_for(action)

    def needs_owner_approval(self, action: ActionRequest, *, is_owner: bool) -> bool:
        sensitivity = self.sensitivity(action)
        if sensitivity is Sensitivity.DANGEROUS:
            return True
        if sensitivity is not Sensitivity.SENSITIVE:
            return False
        return self.confirm_sensitive_actions or (
            self.friends_mode and not is_owner
        )

    @classmethod
    def is_confirmation_only(cls, text: str) -> bool:
        """True only when the whole utterance is a confirmation.

        An action-bearing sentence such as "Sudhir ko call karo confirmed"
        must never approve an older pending action.
        """
        normalized = cls._normalize_confirmation(text)
        if cls.is_negative(normalized):
            return False
        return normalized in cls._CONFIRMATION_PHRASES

    @classmethod
    def is_affirmative(cls, text: str) -> bool:
        """Backward-compatible affirmative detector for non-execution UI use."""
        normalized = cls._normalize_confirmation(text)
        if cls.is_negative(normalized):
            return False
        strong_words = (
            r"\b(?:confirm|confirmed|conform|allow|allowed|approved|proceed)\b"
        )
        return (
            normalized in cls._CONFIRMATION_PHRASES
            or normalized.startswith("yes allow")
            or bool(re.search(strong_words, normalized))
        )

    @staticmethod
    def is_negative(text: str) -> bool:
        normalized = SecurityManager._normalize_confirmation(text)
        phrases = {
            "no",
            "deny",
            "cancel",
            "cancel it",
            "nahi",
            "mat karo",
            "do not allow",
            "do not confirm",
            "dont confirm",
            "reject",
            "stop",
            "ruko",
            "rehne do",
            "नहीं",
            "मत करो",
        }
        return normalized in phrases or bool(
            re.search(r"\b(?:cancel|deny|reject)\b", normalized)
        )

    @staticmethod
    def _normalize_confirmation(text: str) -> str:
        normalized = re.sub(r"[^\w\s']", " ", text.lower(), flags=re.UNICODE)
        return " ".join(normalized.split())
