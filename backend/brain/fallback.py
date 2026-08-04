from __future__ import annotations

import re

from ..models import ActionRequest, BrainResponse
from .whatsapp_intents import whatsapp_end_call_intent


def priority_intent(text: str) -> BrainResponse | None:
    normalized = " ".join(text.lower().replace("’", "'").split())
    end_call = whatsapp_end_call_intent(normalized)
    if end_call:
        return end_call
    enable_phrases = (
        "now you can also listen to my friends",
        "listen to my friends",
        "friends mode on",
        "friend mode on",
        "mere friends ki bhi suno",
        "mere doston ki bhi suno",
    )
    disable_phrases = (
        "stop listening to my friends",
        "friends mode off",
        "friend mode off",
        "mere friends ko sunna band karo",
        "mere doston ko sunna band karo",
    )
    if any(phrase in normalized for phrase in disable_phrases):
        return _action("friend_mode", option="off")
    if any(phrase in normalized for phrase in enable_phrases):
        return _action("friend_mode", option="on")
    return _shopping_intent(normalized) or _fixed_intent(normalized)


def local_intent(text: str) -> BrainResponse:
    normalized = " ".join(text.lower().strip().split())
    if not normalized:
        return BrainResponse("Maine kuch nahi suna. Please dobara boliye.", True)
    end_call = whatsapp_end_call_intent(normalized)
    if end_call:
        return end_call
    fixed = _fixed_intent(normalized)
    if fixed:
        return fixed
    result = (
        _shopping_intent(normalized)
        or _level_intent(normalized)
        or _communication_intent(normalized)
        or _search_and_media_intent(normalized)
        or _open_intent(normalized)
        or _browser_intent(normalized)
    )
    if result:
        return result
    return BrainResponse(
        "Groq key set hone ke baad main is natural request ko samajh paunga. "
        "Abhi aap open, play, search, battery, screenshot ya help bol sakte hain.",
        needs_clarification=True,
    )


def _fixed_intent(text: str) -> BrainResponse | None:
    mappings = (
        (("what can you do", "help", "features batao"), "help"),
        (("stop", "cancel", "ruko", "bas karo"), "stop"),
        (("battery", "charge kitna"), "battery_status"),
        (("screenshot",), "screenshot"),
        (("joke", "chutkula"), "tell_joke"),
        (("poem", "kavita"), "tell_poem"),
    )
    for phrases, name in mappings:
        if any(phrase in text for phrase in phrases):
            return _action(name)
    if "internet" in text and "speed" in text:
        return _action("internet_speed")
    if "download" in text and "video" in text:
        return _action("download_current_video")
    if "shutdown" in text or "computer band" in text:
        return _action("system_action", option="shutdown")
    if "restart" in text:
        return _action("system_action", option="restart")
    if "lock" in text and ("computer" in text or "screen" in text):
        return _action("system_action", option="lock")
    sleep_phrases = (
        "sleep the pc",
        "sleep the computer",
        "put pc to sleep",
        "put computer to sleep",
        "computer sleep",
        "laptop sleep",
        "pc sleep",
        "system sleep",
        "suspend computer",
    )
    if any(phrase in text for phrase in sleep_phrases):
        return _action("system_action", option="sleep")
    return None


def _shopping_intent(text: str) -> BrainResponse | None:
    products = (
        "kapde",
        "shirt",
        "tshirt",
        "t shirt",
        "jeans",
        "shoes",
        "dress",
        "jacket",
        "kurta",
    )
    wants_search = any(
        word in text for word in ("dhundo", "dhoondo", "find", "dikhao", "search")
    )
    mentions_product = "flipkart" in text or any(word in text for word in products)
    if not (wants_search and mentions_product):
        return None
    query = re.sub(
        r"\b(?:flipkart|par|pe|mere|liye|mujhe|ye|search|find|dhundo|"
        r"dhoondo|dikhao|karo|kar do)\b",
        " ",
        text,
    )
    return _action(
        "shopping",
        option="search",
        query=" ".join(query.split()) or "kapde",
    )


def _level_intent(text: str) -> BrainResponse | None:
    for word, name in (("volume", "set_volume"), ("brightness", "set_brightness")):
        match = re.search(rf"(?:{word}).*?(\d{{1,3}})", text)
        if match:
            return _action(name, value=int(match.group(1)))
    return None


def _communication_intent(text: str) -> BrainResponse | None:
    platform = (
        "web"
        if re.search(r"\b(?:whatsapp\s+web|web\s+whatsapp)\b", text)
        else "desktop"
    )
    cleaned = re.sub(
        r"\b(?:whatsapp\s+web|web\s+whatsapp|whatsapp)"
        r"(?:\s+(?:par|pe|se|app))?\b",
        " ",
        text,
    )
    cleaned = " ".join(cleaned.split())
    message = re.search(
        r"(?:message|msg)\s+(?:to\s+)?(?P<contact>[\w ]+?)\s+"
        r"(?:saying|bolo|likho|that)\s+(?P<message>.+)",
        cleaned,
    ) or re.search(
        r"(?P<contact>[\w .+-]+?)\s+ko\s+(?:message|msg)\s+"
        r"(?:karo|kro|kar do|bhejo|send karo)(?:\s+(?:ki|saying|bolo))?\s+"
        r"(?P<message>.+)",
        cleaned,
    )
    if message:
        return _action(
            "whatsapp_message",
            contact=message.group("contact").strip(),
            message=message.group("message").strip(),
            platform=platform,
        )
    call = re.search(
        r"^(?:call|phone)\s+(?:to\s+)?(?P<contact>[\w ]+)$", cleaned
    ) or re.search(
        r"(?P<contact>[\w .+-]+?)\s+ko\s+(?:call|phone)"
        r"(?:\s+(?:karo|kro|kar do|lagao))?$",
        cleaned,
    )
    if call:
        return _action(
            "whatsapp_call",
            contact=call.group("contact").strip(),
            platform=platform,
        )
    return None


def _search_and_media_intent(text: str) -> BrainResponse | None:
    google = re.search(r"(?:google|search(?: for)?)\s+(?P<query>.+)", text)
    if google:
        return _action("google_search", query=google.group("query"))
    browser = re.search(
        r"\b(?P<browser>brave|chrome|edge|firefox)(?:\s+browser)?\b",
        text,
    )
    youtube = re.search(
        r"\byoutube\s+(?:par|pe|pr|mein|me)\s+(?P<query>.+)",
        text,
    )
    if youtube and re.search(
        r"\b(?:play|chalao|chala do|bajao|baja do)\b",
        youtube.group("query"),
    ):
        query = re.sub(
            r"\b(?:play|chalao|chala do|bajao|baja do|karo|kar do)\b",
            " ",
            youtube.group("query"),
        )
        parameters = {"query": " ".join(query.split())}
        if browser:
            parameters["target"] = browser.group("browser")
        return _action("youtube_play", **parameters)
    play = re.search(
        r"(?:play|bajao|chalao)\s+(?P<query>.+?)"
        r"(?:\s+on\s+(?P<service>youtube|spotify))?$",
        text,
    )
    if not play:
        return None
    name = "spotify_play" if play.group("service") == "spotify" else "youtube_play"
    parameters = {"query": play.group("query").strip()}
    if name == "youtube_play" and browser:
        parameters["target"] = browser.group("browser")
    return _action(name, **parameters)


def _open_intent(text: str) -> BrainResponse | None:
    browser = re.search(
        r"\b(?P<browser>brave|chrome|edge|firefox)(?:\s+browser)?\b",
        text,
    )
    domain = re.search(
        r"(?P<target>(?:https?://)?(?:www\.)?"
        r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
        r"(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+"
        r"(?:/[^\s]*)?)",
        text,
    )
    if domain and re.search(r"\b(?:open|kholo|khol|karo)\b", text):
        parameters = {"target": domain.group("target")}
        if browser:
            parameters["browser"] = browser.group("browser")
        return _action("open_website", **parameters)
    website = re.search(
        r"(?:open|kholo)\s+(?P<target>[\w.-]+)\s+(?:website|site)$", text
    )
    if website:
        parameters = {"target": website.group("target")}
        if browser:
            parameters["browser"] = browser.group("browser")
        return _action("open_website", **parameters)
    trailing = re.search(
        r"(?P<target>[\w .+-]+?)\s+(?:kholo|open karo|start karo)$", text
    )
    if trailing:
        return _action("open_app", target=trailing.group("target").strip())
    app = re.search(
        r"(?:open|start|launch|kholo)\s+(?:app\s+)?(?P<target>[\w .+-]+)", text
    )
    return _action("open_app", target=app.group("target")) if app else None


def _browser_intent(text: str) -> BrainResponse | None:
    options = {
        "new tab": "new_tab",
        "close tab": "close_tab",
        "private window": "private_window",
        "zoom in": "zoom_in",
        "zoom out": "zoom_out",
        "refresh": "refresh",
        "scroll down": "scroll_down",
        "scroll up": "scroll_up",
        "next tab": "next_tab",
        "previous tab": "previous_tab",
        "go back": "back",
        "go forward": "forward",
    }
    for phrase, option in options.items():
        if phrase in text:
            return _action("browser_control", option=option)
    return None


def _action(name: str, **parameters) -> BrainResponse:
    return BrainResponse(actions=[ActionRequest(name, parameters)])
