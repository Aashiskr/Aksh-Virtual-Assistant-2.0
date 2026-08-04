from __future__ import annotations

import threading
from collections import deque


class ConversationMemory:
    """Small in-memory chat history for natural follow-up conversations."""

    def __init__(self, max_messages: int = 12):
        self._messages: deque[dict[str, str]] = deque(maxlen=max_messages)
        self._lock = threading.Lock()

    def messages(self) -> list[dict[str, str]]:
        with self._lock:
            return list(self._messages)

    def remember(self, user_text: str, assistant_text: str) -> None:
        with self._lock:
            self._messages.append({"role": "user", "content": user_text.strip()})
            if assistant_text.strip():
                self._messages.append(
                    {"role": "assistant", "content": assistant_text.strip()}
                )

    def clear(self) -> None:
        with self._lock:
            self._messages.clear()
