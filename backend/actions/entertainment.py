from __future__ import annotations

import random
import webbrowser
from typing import Any

from ..models import ActionResult
from .base import ActionGroup


JOKES = [
    "Programmer ne chai kyun nahi pi? Kyunki usme Java nahi thi.",
    "Computer doctor ke paas kyun gaya? Kyunki usse virus ho gaya tha.",
    "Teacher: homework kahan hai? Student: cloud mein save tha, internet nahi chal raha.",
]

POEMS = [
    "Chhoti si koshish, lamba safar; har din seekho, ban jao behtar.",
    "Raat ke baad savera aata hai; mehnat ka rang zaroor nazar aata hai.",
    "Sapne wahi nahi jo neend mein aaye; sapne woh hain jo tumhe aage badhaye.",
]


class EntertainmentActions(ActionGroup):
    def tell_joke(self, parameters: dict[str, Any]) -> ActionResult:
        return ActionResult(True, random.choice(JOKES))

    def tell_poem(self, parameters: dict[str, Any]) -> ActionResult:
        return ActionResult(True, random.choice(POEMS))

    def play_game(self, parameters: dict[str, Any]) -> ActionResult:
        webbrowser.open("https://www.google.com/search?q=free+browser+games")
        return ActionResult(True, "Browser games dhoondh raha hoon.")

    def mood_support(self, parameters: dict[str, Any]) -> ActionResult:
        text = str(parameters.get("query", "")).strip()
        if not text:
            raise ValueError("Please tell me how you feel")
        from ..capabilities.wellbeing import mood_support

        return ActionResult(True, mood_support(text))

    def time_dj(self, parameters: dict[str, Any]) -> ActionResult:
        from ..capabilities.wellbeing import time_dj

        return ActionResult(True, time_dj())

    def help(self, parameters: dict[str, Any]) -> ActionResult:
        return ActionResult(
            True,
            "Main apps, websites, music, WhatsApp, reminders, meetings, browser "
            "control, screenshots, battery, volume aur brightness handle kar sakta hoon.",
        )

    def stop(self, parameters: dict[str, Any]) -> ActionResult:
        return ActionResult(True, "Okay, current request cancel kar di.")
