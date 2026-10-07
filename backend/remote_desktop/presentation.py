from __future__ import annotations

import threading
from collections.abc import Callable

from .input import PRESENTATION_ZOOM_COMMANDS, normalize_presentation_focus


class PresentationController:
    MINIMUM_ZOOM = 1.0
    MAXIMUM_ZOOM = 4.0
    ZOOM_STEP = 0.25
    ACTIONS = {
        "enable",
        "disable",
        "toggle",
        "next",
        "previous",
        "zoom_in",
        "zoom_out",
        "zoom_reset",
    }

    def __init__(
        self,
        submit_command: Callable[..., None],
        *,
        magnifier_running: Callable[[], bool] = lambda: False,
    ):
        self._submit_command = submit_command
        self._magnifier_running = magnifier_running
        self._enabled = False
        self._zoom = self.MINIMUM_ZOOM
        self._revision = 0
        self._owner: str | None = None
        self._magnifier_touched = False
        self._magnifier_started = False
        self._lock = threading.RLock()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return self._snapshot_locked()

    def submit(
        self,
        owner: str,
        action: object,
        *,
        x: object | None = None,
        y: object | None = None,
    ) -> dict[str, object]:
        normalized = str(action or "").strip().lower()
        focus = normalize_presentation_focus(x, y)
        with self._lock:
            if normalized not in self.ACTIONS:
                raise ValueError("Unsupported presentation action.")
            if focus is not None and normalized not in PRESENTATION_ZOOM_COMMANDS:
                raise ValueError(
                    "Presentation focus is only supported for zoom actions."
                )
            if normalized == "toggle":
                normalized = "disable" if self._enabled else "enable"
            if normalized == "enable":
                return self._enable_locked(str(owner))

            self._require_owner_locked(str(owner))
            if normalized == "disable":
                self._reset_locked(best_effort=False)
            elif normalized in {"next", "previous"}:
                self._submit_command(normalized)
            else:
                self._change_zoom_locked(normalized, focus=focus)
            return self._snapshot_locked()

    def reset(
        self,
        *,
        owner: str | None = None,
        best_effort: bool = True,
    ) -> bool:
        with self._lock:
            if owner is not None and self._owner != str(owner):
                return False
            return self._reset_locked(best_effort=best_effort)

    def _enable_locked(self, owner: str) -> dict[str, object]:
        if self._enabled and self._owner != owner:
            raise ValueError("PPT presentation mode belongs to another session.")
        if not self._enabled:
            self._enabled = True
            self._owner = owner
            self._revision += 1
        return self._snapshot_locked()

    def _require_owner_locked(self, owner: str) -> None:
        if not self._enabled:
            raise ValueError("PPT presentation mode is not enabled.")
        if self._owner != owner:
            raise ValueError("PPT presentation mode belongs to another session.")

    def _change_zoom_locked(
        self,
        action: str,
        *,
        focus: tuple[float, float] | None,
    ) -> None:
        next_zoom = self._zoom
        if action == "zoom_in":
            next_zoom = min(self.MAXIMUM_ZOOM, next_zoom + self.ZOOM_STEP)
        elif action == "zoom_out":
            next_zoom = max(self.MINIMUM_ZOOM, next_zoom - self.ZOOM_STEP)
        else:
            next_zoom = self.MINIMUM_ZOOM

        touched_before = self._magnifier_touched
        if action == "zoom_reset":
            self._restore_magnifier_locked(
                best_effort=False,
                focus=focus,
            )
        elif next_zoom != self._zoom:
            was_running = True
            if action == "zoom_in" and not self._magnifier_touched:
                was_running = self._magnifier_running()
            self._submit_zoom_command_locked(action, focus=focus)
            if action == "zoom_in" and not self._magnifier_touched:
                self._magnifier_touched = True
                self._magnifier_started = not was_running

        state_changed = next_zoom != self._zoom or (
            action == "zoom_reset" and touched_before
        )
        if state_changed:
            self._zoom = next_zoom
            self._revision += 1

    def _reset_locked(self, *, best_effort: bool) -> bool:
        was_active = (
            self._enabled
            or self._zoom != self.MINIMUM_ZOOM
            or self._magnifier_touched
        )
        if not was_active:
            return False
        self._restore_magnifier_locked(best_effort=best_effort)
        self._enabled = False
        self._zoom = self.MINIMUM_ZOOM
        self._owner = None
        self._revision += 1
        return True

    def _restore_magnifier_locked(
        self,
        *,
        best_effort: bool,
        focus: tuple[float, float] | None = None,
    ) -> None:
        if not self._magnifier_touched:
            return
        commands = ["zoom_reset"] if self._magnifier_started else [
            "zoom_out"
        ] * round((self._zoom - self.MINIMUM_ZOOM) / self.ZOOM_STEP)
        try:
            for index, command in enumerate(commands):
                self._submit_zoom_command_locked(
                    command,
                    focus=focus if index == 0 else None,
                )
        except RuntimeError:
            if not best_effort:
                raise
        self._magnifier_touched = False
        self._magnifier_started = False

    def _submit_zoom_command_locked(
        self,
        command: str,
        *,
        focus: tuple[float, float] | None,
    ) -> None:
        if focus is None:
            self._submit_command(command)
            return
        self._submit_command(command, x=focus[0], y=focus[1])

    def _snapshot_locked(self) -> dict[str, object]:
        return {
            "enabled": self._enabled,
            "zoom": self._zoom,
            "revision": self._revision,
        }
