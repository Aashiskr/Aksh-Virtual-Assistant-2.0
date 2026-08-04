from __future__ import annotations

import logging
from pathlib import Path


LOGGER = logging.getLogger(__name__)
DEFAULT_ICON = (
    Path(__file__).resolve().parents[1]
    / "frontend"
    / "desktop"
    / "assets"
    / "aksh_pet.png"
)


def show_notification(text: str, icon: Path | None = DEFAULT_ICON) -> None:
    try:
        from winotify import Notification, audio

        toast = Notification(
            app_id="Aksh",
            title="Aksh",
            msg=text,
            duration="short",
            icon=str(icon) if icon and icon.exists() else "",
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
    except Exception as exc:
        LOGGER.debug("Notification failed: %s", exc)
