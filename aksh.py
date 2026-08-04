"""Aksh AI desktop pet launcher."""

import os
import sys


def _prepare_windowed_streams() -> None:
    """Give pythonw-based launches safe streams before importing the app."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


_prepare_windowed_streams()

from frontend.desktop.app import main  # noqa: E402


if __name__ == "__main__":
    main()
