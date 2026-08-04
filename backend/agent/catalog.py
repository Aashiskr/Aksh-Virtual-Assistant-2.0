from __future__ import annotations

from dataclasses import dataclass

from ..models import ActionRequest, Sensitivity


@dataclass(frozen=True, slots=True)
class ActionSpec:
    name: str
    parameters: str
    description: str
    sensitivity: Sensitivity = Sensitivity.SAFE


ACTION_SPECS = (
    ActionSpec("open_app", "target", "open a Windows application"),
    ActionSpec(
        "open_website",
        "target, browser",
        "open a website in an optional named browser",
    ),
    ActionSpec("google_search", "query", "search Google"),
    ActionSpec(
        "youtube_play",
        "query, target",
        "resolve and play YouTube content; target is an optional named browser",
    ),
    ActionSpec("spotify_play", "query", "find Spotify content"),
    ActionSpec("browser_control", "option", "control the active browser"),
    ActionSpec("youtube_control", "option", "control the active YouTube tab"),
    ActionSpec("window_control", "option", "control the active window"),
    ActionSpec("switch_window", "target", "switch to an open application"),
    ActionSpec(
        "whatsapp_message",
        "contact, message, platform",
        "send a WhatsApp message",
        Sensitivity.SENSITIVE,
    ),
    ActionSpec(
        "whatsapp_call",
        "contact, platform",
        "start a WhatsApp call",
        Sensitivity.SENSITIVE,
    ),
    ActionSpec(
        "whatsapp_end_call",
        "platform",
        "end the active or still-ringing WhatsApp call",
    ),
    ActionSpec("battery_status", "", "report battery status"),
    ActionSpec("screenshot", "", "save a screenshot"),
    ActionSpec("internet_speed", "", "estimate internet download speed"),
    ActionSpec("set_reminder", "message, time", "create a reminder"),
    ActionSpec("set_alarm", "time", "create an alarm"),
    ActionSpec(
        "download_current_video",
        "",
        "download the active browser video",
        Sensitivity.SENSITIVE,
    ),
    ActionSpec(
        "schedule_meeting",
        "time",
        "create a meeting",
        Sensitivity.SENSITIVE,
    ),
    ActionSpec(
        "send_meeting",
        "contact, time",
        "send a saved meeting link",
        Sensitivity.SENSITIVE,
    ),
    ActionSpec("tell_joke", "", "tell a joke"),
    ActionSpec("tell_poem", "", "tell a short poem"),
    ActionSpec("play_game", "option", "open a game"),
    ActionSpec("mood_support", "query", "offer mood support and suitable media"),
    ActionSpec("time_dj", "", "play time-appropriate media"),
    ActionSpec("english_tutor", "query", "coach one English sentence"),
    ActionSpec(
        "fill_form",
        "target",
        "read fields from an image without submitting",
        Sensitivity.SENSITIVE,
    ),
    ActionSpec("set_volume", "value", "change system volume"),
    ActionSpec("set_brightness", "value", "change display brightness"),
    ActionSpec(
        "system_action",
        "option",
        "shutdown, restart, lock, or sleep the computer",
        Sensitivity.DANGEROUS,
    ),
    ActionSpec("friend_mode", "option", "change who Aksh listens to"),
    ActionSpec("help", "", "explain available features"),
    ActionSpec("stop", "", "stop the current request"),
    ActionSpec("shopping", "option, query", "control a Flipkart browsing session"),
)

ACTION_CATALOG = {spec.name: spec for spec in ACTION_SPECS}
ACTION_NAMES = tuple(ACTION_CATALOG)
EXECUTOR_ACTION_NAMES = ("friend_mode",)
TERMINAL_ACTION_NAMES = ("stop", "system_action")
PARAMETER_KEYS = (
    "target",
    "query",
    "contact",
    "message",
    "platform",
    "time",
    "value",
    "option",
    "browser",
)


def sensitivity_for(action: ActionRequest | str) -> Sensitivity:
    if isinstance(action, ActionRequest):
        if (
            action.name == "shopping"
            and action.parameters.get("option") == "add_cart"
        ):
            return Sensitivity.SENSITIVE
        name = action.name
    else:
        name = action
    spec = ACTION_CATALOG.get(name)
    return spec.sensitivity if spec else Sensitivity.SAFE


def prompt_reference() -> str:
    return "\n".join(
        f"- {spec.name}"
        + (f" ({spec.parameters})" if spec.parameters else "")
        + f": {spec.description}"
        for spec in ACTION_SPECS
    )
