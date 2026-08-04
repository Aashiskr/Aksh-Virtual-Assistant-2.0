from __future__ import annotations

import re

from .whatsapp_controls import find_edit
from .whatsapp_names import base_contact_name, display_contact_name


MESSAGE_PREFIX = re.compile(
    r"^\s*(?:type\s+a\s+message|message)(?:\s+to)?\s*",
    re.IGNORECASE,
)
LEADING_PHONE = re.compile(r"^\s*(?:\+|00)?[\d\s().-]{7,}")


def control_name(control) -> str:
    if control is None:
        return ""
    return (control.element_info.name or "").strip()


def leading_phone_digits(value: str) -> str:
    match = LEADING_PHONE.match(str(value))
    return re.sub(r"\D", "", match.group(0)) if match else ""


def phone_targets_match(requested: str, candidate: str) -> bool:
    target = leading_phone_digits(requested)
    found = leading_phone_digits(candidate)
    if not target or not found:
        return False
    if target == found:
        return True
    return (
        len(target) == 10
        and len(found) > len(target)
        and found.endswith(target)
    )


def editor_matches_target(editor, requested: str, selected_name: str) -> bool:
    recipient = MESSAGE_PREFIX.sub("", control_name(editor))
    phone_identity = leading_phone_digits(selected_name)
    if phone_identity or leading_phone_digits(requested):
        return phone_targets_match(selected_name or requested, recipient) or (
            phone_targets_match(requested, recipient)
        )

    recipient_name = base_contact_name(recipient)
    identities = {
        base_contact_name(display_contact_name(value))
        for value in (selected_name, requested)
        if value
    }
    return any(
        identity
        and (
            recipient_name == identity
            or recipient_name.startswith(f"{identity} ")
        )
        for identity in identities
    )


def find_target_editor(
    window,
    labels,
    requested: str,
    selected_name: str,
):
    editor = find_edit(window, labels)
    if editor and editor_matches_target(editor, requested, selected_name):
        return editor
    return None


def find_phone_target_editor(
    window,
    labels,
    phone_number: str,
    previous_editor_name: str,
):
    editor = find_edit(window, labels)
    if editor is None:
        return None
    if editor_matches_target(editor, phone_number, phone_number):
        return editor
    if not previous_editor_name or control_name(editor) != previous_editor_name:
        return editor
    return None
