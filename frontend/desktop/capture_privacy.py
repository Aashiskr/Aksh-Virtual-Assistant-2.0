from __future__ import annotations

import ctypes
import logging
import sys


LOGGER = logging.getLogger(__name__)
WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011
GA_ROOT = 2


def set_capture_excluded(widget, excluded: bool = True) -> bool:
    """Hide this process-owned top-level window from supported capture APIs."""
    if sys.platform != "win32":
        return False
    try:
        widget.update_idletasks()
        child = int(widget.winfo_id())
        user32 = ctypes.windll.user32
        hwnd = int(user32.GetAncestor(child, GA_ROOT)) or child
        affinity = WDA_EXCLUDEFROMCAPTURE if excluded else WDA_NONE
        success = bool(user32.SetWindowDisplayAffinity(hwnd, affinity))
        if not success:
            error = ctypes.get_last_error()
            LOGGER.warning(
                "Screen-capture exclusion failed: hwnd=%s error=%s",
                hwnd,
                error,
            )
        return success
    except Exception as exc:
        LOGGER.warning("Screen-capture exclusion unavailable: %s", exc)
        return False
