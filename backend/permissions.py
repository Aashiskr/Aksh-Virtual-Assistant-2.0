from __future__ import annotations

from typing import Callable

from .models import ActionRequest
from .security import SecurityManager


def action_description(action: ActionRequest) -> str:
    labels = {
        "whatsapp_message": "send a WhatsApp message",
        "whatsapp_call": "start a WhatsApp call",
        "whatsapp_end_call": "end the WhatsApp call",
        "schedule_meeting": "create a meeting",
        "send_meeting": "send a meeting link",
        "fill_form": "read fields from an image",
        "download_current_video": "download the current video",
        "system_action": (
            f"{action.parameters.get('option', 'system action')} the computer"
        ),
        "shopping": "change the current shopping session",
    }
    base = labels.get(action.name, action.name.replace("_", " "))
    if action.name == "whatsapp_message":
        contact = action.parameters.get("contact", "contact")
        preview = str(action.parameters.get("message", ""))[:80]
        return f"send WhatsApp message to {contact}: {preview}"
    if action.name == "schedule_meeting":
        when = action.parameters.get("time", "requested time")
        account = action.parameters.get("account")
        source = f" from {account} account" if account else ""
        return f"create a meeting at {when}{source}"
    target = (
        action.parameters.get("contact")
        or action.parameters.get("target")
        or action.parameters.get("query")
    )
    return f"{base}: {target}" if target else base


class FriendModeController:
    def __init__(
        self,
        security: SecurityManager,
        status: Callable[[str, str], None],
        say: Callable[[str], None],
    ):
        self.security = security
        self.status = status
        self.say = say

    def handle(self, action: ActionRequest, *, is_owner: bool) -> None:
        option = str(action.parameters.get("option", "")).lower()
        enabled = option in {"on", "enable", "enabled", "true"}
        if not is_owner:
            self.status("locked", "Only owner can change Friends Mode")
            self.say("Friends Mode sirf owner ki verified voice change kar sakti hai.")
            return
        if not self.security.set_friends_mode(
            enabled, requested_by_owner=is_owner
        ):
            self.say("Friends Mode change nahi hua.")
            return
        if enabled:
            self.status("friends", "Friends Mode · permission guard active")
            self.say(
                "Friends Mode enabled. Main sabki normal commands sununga aur "
                "sensitive actions ke liye aapse permission maangunga."
            )
        else:
            self.status("idle", "Owner-only mode")
            self.say("Friends Mode off. Ab main sirf aapki verified voice sununga.")
