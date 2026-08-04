from __future__ import annotations

import logging
import threading
from datetime import datetime

import psutil


LOGGER = logging.getLogger(__name__)


class SmartEnvironmentMonitor:
    """Temporarily adapts volume and brightness, then restores prior values."""

    def __init__(self, interval_seconds: float = 5.0):
        self.interval = interval_seconds
        self._stop = threading.Event()
        self._thread = None
        self._saved_volume: float | None = None
        self._saved_brightness: int | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run, name="aksh-smart-environment", daemon=True
        )
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        self._restore_volume()
        self._restore_brightness()

    def _run(self) -> None:
        try:
            import pythoncom

            pythoncom.CoInitialize()
        except Exception:
            pass
        while not self._stop.is_set():
            try:
                self._update_whatsapp_volume()
                self._update_night_brightness()
            except Exception as exc:
                LOGGER.debug("Smart environment check failed: %s", exc)
            if self._stop.wait(self.interval):
                return

    def _update_whatsapp_volume(self) -> None:
        process_names = {
            process.info["name"].lower()
            for process in psutil.process_iter(["name"])
            if process.info.get("name")
        }
        active = "whatsapp.exe" in process_names
        endpoint = self._volume_endpoint()
        if endpoint is None:
            return
        if active and self._saved_volume is None:
            current = float(endpoint.GetMasterVolumeLevelScalar())
            self._saved_volume = current
            endpoint.SetMasterVolumeLevelScalar(min(current, 0.10), None)
        elif not active and self._saved_volume is not None:
            self._restore_volume(endpoint)

    def _update_night_brightness(self) -> None:
        import screen_brightness_control as sbc

        is_night = datetime.now().hour >= 19 or datetime.now().hour < 6
        if is_night and self._saved_brightness is None:
            current = int(sbc.get_brightness(display=0)[0])
            self._saved_brightness = current
            sbc.set_brightness(min(current, 20), display=0)
        elif not is_night and self._saved_brightness is not None:
            self._restore_brightness()

    @staticmethod
    def _volume_endpoint():
        try:
            from pycaw.pycaw import AudioUtilities

            return AudioUtilities.GetSpeakers().EndpointVolume
        except Exception:
            return None

    def _restore_volume(self, endpoint=None) -> None:
        if self._saved_volume is None:
            return
        endpoint = endpoint or self._volume_endpoint()
        if endpoint:
            try:
                endpoint.SetMasterVolumeLevelScalar(self._saved_volume, None)
            except Exception:
                pass
        self._saved_volume = None

    def _restore_brightness(self) -> None:
        if self._saved_brightness is None:
            return
        try:
            import screen_brightness_control as sbc

            sbc.set_brightness(self._saved_brightness, display=0)
        except Exception:
            pass
        self._saved_brightness = None
