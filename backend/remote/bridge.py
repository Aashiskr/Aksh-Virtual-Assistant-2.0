from __future__ import annotations

import threading
from collections.abc import Callable

from ..command_runtime import CommandRuntime


class RemoteCommandRunner:
    def __init__(
        self,
        *,
        closing: threading.Event,
        active_lock: threading.Lock,
        runtime: CommandRuntime,
        process: Callable[..., str],
        message: Callable[[str, str], None],
    ):
        self.closing = closing
        self.active_lock = active_lock
        self.runtime = runtime
        self.process = process
        self.message = message

    def run(self, text: str) -> str:
        if not text.strip() or self.closing.is_set():
            raise RuntimeError("Aksh remote command accept nahi kar sakta.")
        if not self.active_lock.acquire(timeout=45.0):
            raise RuntimeError(
                "Aksh 45 seconds se busy hai; command dobara bhejiye."
            )
        reports: list[str] = []
        errors: list[Exception] = []

        def operation() -> None:
            try:
                self.message("you", text)
                reports.append(
                    self.process(text, is_owner=True, source="phone")
                )
            except Exception as exc:
                errors.append(exc)
                raise

        self.runtime.run(operation, "phone")
        if errors:
            raise RuntimeError(str(errors[0])) from errors[0]
        return reports[0] if reports else "Command process ho gaya."
