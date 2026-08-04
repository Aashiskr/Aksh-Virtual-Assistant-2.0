from __future__ import annotations

import re

from .whatsapp_names import base_contact_name
from .whatsapp_phone import normalize_whatsapp_number


def contact_search_queries(value: str, *, limit: int = 8) -> list[str]:
    """Builds bounded Indian-name spelling variants for UI search retries."""
    raw = str(value).strip()
    if normalize_whatsapp_number(raw):
        return [raw]
    target = base_contact_name(raw) or raw.casefold()
    queries = [target]
    frontier = [target]
    while frontier and len(queries) < limit:
        current = frontier.pop(0)
        for candidate in _phonetic_variants(current):
            if candidate and candidate not in queries:
                queries.append(candidate)
                frontier.append(candidate)
                if len(queries) >= limit:
                    break
    return queries


def _phonetic_variants(value: str) -> list[str]:
    candidates: list[str] = []
    replacements = (
        (r"i", "ee"),
        (r"([bcdfgjklmnpqrstvwxyz])hi", r"\1ee"),
        (r"ee", "i"),
        (r"oo", "u"),
        (r"u", "oo"),
        (r"aa", "a"),
    )
    for pattern, replacement in replacements:
        candidate = re.sub(pattern, replacement, value, count=1)
        if candidate != value:
            candidates.append(candidate)
    without_soft_h = re.sub(r"h(?=(?:ee|[aeiou]))", "", value, count=1)
    if without_soft_h != value:
        candidates.append(without_soft_h)
    return candidates
