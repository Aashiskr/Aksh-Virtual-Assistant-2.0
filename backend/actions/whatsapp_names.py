from __future__ import annotations

import re
import unicodedata


HONORIFICS = {
    "aunty",
    "bhai",
    "bro",
    "jee",
    "ji",
    "maam",
    "madam",
    "mam",
    "saab",
    "sahab",
    "sir",
    "uncle",
}

ROW_METADATA = re.compile(
    r"\s+(?:"
    r"\d{1,2}:\d{2}\s*(?:am|pm)"
    r"|\d{1,2}/\d{1,2}/\d{2,4}"
    r"|today|yesterday|monday|tuesday|wednesday|thursday|friday"
    r"|saturday|sunday"
    r")(?=\s|$)",
    re.IGNORECASE,
)


def normalize_contact_name(value: str) -> str:
    """Removes emoji/decorations while preserving letters from all scripts."""
    characters: list[str] = []
    for character in unicodedata.normalize("NFKC", value).casefold():
        category = unicodedata.category(character)
        if character.isspace():
            characters.append(" ")
        elif category[0] in {"L", "N"}:
            characters.append(character)
        elif category[0] == "M" and ord(character) != 0xFE0F:
            characters.append(character)
    return " ".join("".join(characters).split())


def base_contact_name(value: str) -> str:
    return " ".join(
        token
        for token in normalize_contact_name(value).split()
        if token not in HONORIFICS
    )


def phonetic_contact_name(value: str) -> str:
    compact = base_contact_name(value).replace(" ", "")
    for source, target in (("ee", "i"), ("oo", "u"), ("aa", "a")):
        compact = compact.replace(source, target)
    return compact


def display_contact_name(value: str) -> str:
    """Extracts the name from a WhatsApp row containing time/preview text."""
    metadata = ROW_METADATA.search(value)
    return value[: metadata.start()].strip() if metadata else value.strip()


def choose_contact_name(requested: str, candidates: list[str]) -> str | None:
    target = base_contact_name(requested)
    if not target:
        return None
    normalized: dict[str, str] = {}
    for candidate in candidates:
        if "is also in this group" in normalize_contact_name(candidate):
            continue
        name = base_contact_name(display_contact_name(candidate))
        if name:
            normalized.setdefault(name, candidate)
    if target in normalized:
        return normalized[target]
    prefixes = {
        name: original
        for name, original in normalized.items()
        if name.startswith(f"{target} ")
    }
    if len(prefixes) == 1:
        return next(iter(prefixes.values()))
    target_sound = phonetic_contact_name(target)
    phonetic = {
        name: original
        for name, original in normalized.items()
        if phonetic_contact_name(name) == target_sound
        or (
            len(target.split()) == 1
            and phonetic_contact_name(name.split()[0]) == target_sound
        )
    }
    return next(iter(phonetic.values())) if len(phonetic) == 1 else None
