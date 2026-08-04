from __future__ import annotations

import logging
import queue
import threading
import time

from .neural import NeuralVoice


LOGGER = logging.getLogger(__name__)


class Speaker:
    """Serializes speech so concurrent Aksh tasks never talk over each other."""

    def __init__(
        self,
        rate: int = 180,
        *,
        neural_voice: str = "hi-IN-MadhurNeural",
        neural_rate: str = "+4%",
        neural_pitch: str = "-8Hz",
        neural_volume: str = "+8%",
    ):
        self.rate = rate
        self.neural = NeuralVoice(
            neural_voice, neural_rate, neural_pitch, neural_volume
        )
        self._queue: queue.Queue[tuple[str, threading.Event | None] | None] = queue.Queue()
        self._stop = threading.Event()
        self._muted = threading.Event()
        self._latest_lock = threading.Lock()
        self._latest_finished = threading.Event()
        self._latest_finished.set()
        self._engine = None
        self._thread = threading.Thread(
            target=self._worker, name="aksh-speaker", daemon=True
        )
        self._thread.start()

    def speak(self, text: str, *, block: bool = False) -> None:
        clean = " ".join(str(text).strip().split())
        if not clean or self._muted.is_set():
            return
        finished = threading.Event()
        with self._latest_lock:
            self._latest_finished = finished
        self._queue.put((clean, finished))
        if block:
            finished.wait(timeout=max(15.0, len(clean) / 8))

    def wait_until_idle(self, timeout: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._latest_lock:
                latest = self._latest_finished
            if not latest.wait(timeout=max(0.0, deadline - time.monotonic())):
                return False
            with self._latest_lock:
                if latest is self._latest_finished:
                    return True
        return False

    def stop_current(self) -> None:
        try:
            if self._engine:
                self._engine.stop()
        except Exception:
            pass

    def set_muted(self, muted: bool) -> None:
        if muted:
            self._muted.set()
            self.stop_current()
        else:
            self._muted.clear()

    def close(self) -> None:
        self._stop.set()
        self._queue.put(None)

    def _worker(self) -> None:
        try:
            import pythoncom
            import pyttsx3

            pythoncom.CoInitialize()
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.rate)
        except Exception as exc:
            LOGGER.warning("Offline TTS could not start: %s", exc)

        while not self._stop.is_set():
            item = self._queue.get()
            if item is None:
                break
            text, finished = item
            try:
                if self._muted.is_set():
                    continue
                try:
                    self.neural.speak(text)
                except Exception as neural_error:
                    LOGGER.warning("Neural TTS failed; using offline voice: %s", neural_error)
                    if not self._engine:
                        raise
                    self._engine.say(text)
                    self._engine.runAndWait()
            except Exception as exc:
                LOGGER.warning("TTS failed: %s", exc)
                print(f"Aksh: {text}")
            finally:
                finished.set()
