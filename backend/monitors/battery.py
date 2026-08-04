from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import psutil


class BatteryMonitor:
    def __init__(
        self,
        on_alert,
        interval_seconds: float = 20.0,
        *,
        state_path: Path | None = None,
        full_warning_limit: int = 2,
        full_warning_cooldown_seconds: float = 30 * 60,
        clock=time.time,
    ):
        self.on_alert = on_alert
        self.interval = interval_seconds
        self.state_path = state_path
        self.full_warning_limit = max(0, int(full_warning_limit))
        self.full_warning_cooldown = max(
            0.0,
            float(full_warning_cooldown_seconds),
        )
        self.clock = clock
        self._stop = threading.Event()
        self._thread = None
        self._previous_plugged: bool | None = None
        self._announced_levels: set[int] = set()
        self._full_warning_count = 0
        self._last_full_warning_at = 0.0
        self._load_state()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run,
            name="aksh-battery",
            daemon=True,
        )
        self._thread.start()

    def close(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            battery = psutil.sensors_battery()
            if battery is None:
                return
            plugged = bool(battery.power_plugged)
            percentage = int(battery.percent)
            self._check_plug_state(plugged)
            self._check_level(percentage, plugged)
            if self._stop.wait(self.interval):
                return

    def _check_plug_state(self, plugged: bool) -> None:
        changed = (
            self._previous_plugged is not None
            and plugged != self._previous_plugged
        )
        if changed:
            self._announced_levels.clear()
            self._reset_full_warnings()
            self.on_alert(
                "Charging started." if plugged else "Charger unplugged."
            )
        self._previous_plugged = plugged
        if changed:
            self._save_state()

    def _check_level(self, percentage: int, plugged: bool) -> None:
        if plugged:
            if percentage <= 95 and self._full_warning_count:
                self._reset_full_warnings()
                self._save_state()
            if percentage >= 100 and self._full_warning_due():
                self.on_alert(
                    "Battery is fully charged. You can unplug the charger."
                )
                self._full_warning_count += 1
                self._last_full_warning_at = self.clock()
                self._save_state()
            return
        for threshold, message in (
            (5, "Battery is critically low at 5 percent. Please charge now."),
            (10, "Battery is very low at 10 percent."),
            (20, "Battery is low at 20 percent."),
        ):
            if percentage <= threshold and threshold not in self._announced_levels:
                self.on_alert(message)
                self._announced_levels.add(threshold)
                break

    def _full_warning_due(self) -> bool:
        if self._full_warning_count >= self.full_warning_limit:
            return False
        if self._full_warning_count == 0:
            return True
        return (
            self.clock() - self._last_full_warning_at
            >= self.full_warning_cooldown
        )

    def _reset_full_warnings(self) -> None:
        self._full_warning_count = 0
        self._last_full_warning_at = 0.0

    def _load_state(self) -> None:
        if self.state_path is None:
            return
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
            previous = value.get("previous_plugged")
            if isinstance(previous, bool):
                self._previous_plugged = previous
            self._full_warning_count = min(
                self.full_warning_limit,
                max(0, int(value.get("full_warning_count", 0))),
            )
            self._last_full_warning_at = max(
                0.0,
                float(value.get("last_full_warning_at", 0.0)),
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return

    def _save_state(self) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "previous_plugged": self._previous_plugged,
                    "full_warning_count": self._full_warning_count,
                    "last_full_warning_at": self._last_full_warning_at,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.state_path)
