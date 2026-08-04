from __future__ import annotations

import logging
from typing import Any, Callable

from ..config import AkshSettings
from ..models import ActionRequest, ActionResult
from .communication import CommunicationActions
from .desktop import DesktopActions
from .entertainment import EntertainmentActions
from .productivity import ProductivityActions
from .web_media import WebMediaActions
from ..shopping import ShoppingActions


LOGGER = logging.getLogger(__name__)


class ActionRegistry:
    def __init__(
        self,
        settings: AkshSettings,
        *,
        on_reminder: Callable[[dict[str, Any]], None],
    ):
        self.desktop = DesktopActions(settings)
        self.web = WebMediaActions(settings)
        self.communication = CommunicationActions(settings)
        self.productivity = ProductivityActions(settings, on_reminder)
        self.entertainment = EntertainmentActions(settings)
        self.shopping = ShoppingActions(settings)
        self.handlers = self._handler_map()

    def _handler_map(self):
        return {
            "open_app": self.desktop.open_app,
            "browser_control": self.desktop.browser_control,
            "youtube_control": self.desktop.youtube_control,
            "window_control": self.desktop.window_control,
            "switch_window": self.desktop.switch_window,
            "battery_status": self.desktop.battery_status,
            "screenshot": self.desktop.screenshot,
            "set_volume": self.desktop.set_volume,
            "set_brightness": self.desktop.set_brightness,
            "system_action": self.desktop.system_action,
            "open_website": self.web.open_website,
            "google_search": self.web.google_search,
            "youtube_play": self.web.youtube_play,
            "spotify_play": self.web.spotify_play,
            "internet_speed": self.web.internet_speed,
            "download_current_video": self.web.download_current_video,
            "whatsapp_message": self.communication.whatsapp_message,
            "whatsapp_call": self.communication.whatsapp_call,
            "whatsapp_end_call": self.communication.whatsapp_end_call,
            "schedule_meeting": self.communication.schedule_meeting,
            "send_meeting": self.communication.send_meeting,
            "set_reminder": self.productivity.set_reminder,
            "set_alarm": self.productivity.set_alarm,
            "english_tutor": self.productivity.english_tutor,
            "fill_form": self.productivity.fill_form,
            "tell_joke": self.entertainment.tell_joke,
            "tell_poem": self.entertainment.tell_poem,
            "play_game": self.entertainment.play_game,
            "mood_support": self.entertainment.mood_support,
            "time_dj": self.entertainment.time_dj,
            "help": self.entertainment.help,
            "stop": self.entertainment.stop,
            "shopping": self.shopping.execute,
        }

    def start(self) -> None:
        self.productivity.start()

    def close(self) -> None:
        self.productivity.close()
        self.shopping.close()

    def execute(self, action: ActionRequest) -> ActionResult:
        handler = self.handlers.get(action.name)
        if not handler:
            return ActionResult(False, f"Action '{action.name}' available nahi hai.")
        try:
            return handler(action.parameters)
        except Exception as exc:
            LOGGER.exception("Action %s failed", action.name)
            return ActionResult(False, f"{action.name} complete nahi hua: {exc}")
