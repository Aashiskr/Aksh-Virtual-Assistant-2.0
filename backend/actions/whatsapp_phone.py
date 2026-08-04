from __future__ import annotations

import re


PHONE_CHARACTERS = re.compile(r"^\s*(?:\+|00)?[\d\s().-]{7,}\s*$")


def normalize_whatsapp_number(
    value: str,
    *,
    default_country_code: str = "91",
) -> str | None:
    """Returns WhatsApp's digits-only international number format.

    A bare 10-digit number is treated as an Indian mobile number. Explicit
    international prefixes (+ or 00) and already-prefixed numbers are kept.
    """
    raw = str(value).strip()
    if not PHONE_CHARACTERS.fullmatch(raw):
        return None
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("00"):
        digits = digits[2:]
    if not 7 <= len(digits) <= 15:
        return None
    if raw.startswith("+") or raw.startswith("00"):
        return digits
    if len(digits) == 10:
        return f"{default_country_code}{digits}"
    if len(digits) == 11 and digits.startswith("0"):
        return f"{default_country_code}{digits[1:]}"
    return digits
