from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager


LOGGER = logging.getLogger(__name__)


def _speaker_endpoint():
    from pycaw.pycaw import AudioUtilities

    return AudioUtilities.GetSpeakers().EndpointVolume


@contextmanager
def mute_output_while_listening(enabled: bool = True) -> Iterator[None]:
    """Temporarily mute the default output and restore its prior mute state."""

    endpoint = None
    changed_mute = False
    com_runtime = None
    if enabled:
        try:
            import pythoncom

            pythoncom.CoInitialize()
            com_runtime = pythoncom
        except Exception:
            pass
        try:
            endpoint = _speaker_endpoint()
            if not bool(endpoint.GetMute()):
                endpoint.SetMute(1, None)
                changed_mute = True
                LOGGER.info("System output muted while command microphone is open")
                time.sleep(0.25)
        except Exception as exc:
            LOGGER.debug("System output could not be muted: %s", exc)

    try:
        yield
    finally:
        if changed_mute and endpoint is not None:
            try:
                endpoint.SetMute(0, None)
                LOGGER.info("System output mute state restored")
            except Exception as exc:
                LOGGER.warning("System output mute state restore failed: %s", exc)
        if com_runtime is not None:
            try:
                com_runtime.CoUninitialize()
            except Exception:
                pass
