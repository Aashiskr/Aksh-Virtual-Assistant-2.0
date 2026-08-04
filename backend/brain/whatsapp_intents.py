from __future__ import annotations

import re

from ..models import ActionRequest, BrainResponse


def whatsapp_end_call_intent(text: str) -> BrainResponse | None:
    has_call_word = bool(
        re.search(r"\b(?:call|phone)\b", text)
        or "कॉल" in text
        or "फ़ोन" in text
        or "फोन" in text
    )
    imperative = bool(
        re.search(
            r"\b(?:cut|end|stop|cancel|disconnect)\s+"
            r"(?:(?:the|this|whatsapp)\s+)?call\b",
            text,
        )
        or re.search(
            r"\b(?:call|phone)(?:\s+ko)?\s+"
            r"(?:cut|end|stop|cancel|disconnect|band|kaat|kat|hata)"
            r"(?:\s+(?:kar|karo|kro|kar do|kr do|kar de|kr de|do|de))?\b",
            text,
        )
        or re.search(r"\bhang\s*up\b", text)
        or (
            has_call_word
            and any(
                phrase in text
                for phrase in (
                    "kaat do",
                    "kaat de",
                    "kat do",
                    "kat de",
                    "band kar",
                    "बंद कर",
                    "काट दो",
                    "काट दे",
                )
            )
        )
    )
    if not (has_call_word and imperative):
        return None
    platform = (
        "web"
        if re.search(r"\b(?:whatsapp\s+web|web\s+whatsapp)\b", text)
        else "desktop"
    )
    return BrainResponse(
        actions=[
            ActionRequest(
                "whatsapp_end_call",
                {"platform": platform},
            )
        ]
    )
