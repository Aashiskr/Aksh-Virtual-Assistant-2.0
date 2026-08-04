from __future__ import annotations

import re


MIC_OFF_PHRASES = {
    "deactivate",
    "deactivate yourself",
    "go to sleep",
    "listening band karo",
    "mic band karo",
    "mic off",
    "mic off kar lo",
    "microphone band karo",
    "microphone off",
    "stop listening",
    "sunna band karo",
    "ab mat suno",
}

MIC_WORD = r"(?:mic|mik|mike|maik|microphone|micro\s+phone)"
OFF_WORD = r"(?:off|band|close)"


def is_mic_off_command(text: str) -> bool:
    normalized = re.sub(r"[^\w\s]", " ", text.lower(), flags=re.UNICODE)
    normalized = " ".join(normalized.split())
    if normalized in MIC_OFF_PHRASES:
        return True
    negative = (
        rf"\b{MIC_WORD}\b.*\b{OFF_WORD}\b.*\b(?:mat|nahi)\b"
        rf"|\b{MIC_WORD}\b.*\b(?:mat|nahi)\b.*\b{OFF_WORD}\b"
    )
    if re.search(negative, normalized):
        return False
    return bool(
        re.search(rf"\b{MIC_WORD}\b.*\b{OFF_WORD}\b", normalized)
        or re.search(rf"\b{OFF_WORD}\b.*\b{MIC_WORD}\b", normalized)
    )
