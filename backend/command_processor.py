from __future__ import annotations

import re
from collections.abc import Callable

from .actions import ActionRegistry
from .agent.executor import AgentExecutor
from .audio import is_mic_off_command
from .brain import GroqBrain
from .brain.fallback import local_intent
from .confirmations import ConfirmationManager, ConfirmationResolution
from .models import ActionRequest, BrainResponse
from .permissions import FriendModeController, action_description
from .security import SecurityManager


_STRONG_CONFIRMATION_MARKER = re.compile(
    r"\b(?:confirm(?:ed)?|conform|approved?|allow(?:ed)?|proceed)\b",
    re.IGNORECASE,
)
_EDGE_CONFIRMATION_MARKER = re.compile(
    r"^\s*(?:yes|haan|han|ok(?:ay)?)\b[\s,;:-]*|"
    r"[\s,;:-]*\b(?:yes|haan|han|ok(?:ay)?)\s*$",
    re.IGNORECASE,
)


class CommandProcessor:
    def __init__(
        self,
        *,
        brain: GroqBrain,
        actions: ActionRegistry,
        security: SecurityManager,
        confirmations: ConfirmationManager,
        friend_mode: FriendModeController,
        set_mic: Callable[[bool], None],
        status: Callable[[str, str], None],
        say: Callable[[str], None],
        message: Callable[[str, str], None],
        stop_speaking: Callable[[], None],
    ):
        self.brain = brain
        self.actions = actions
        self.security = security
        self.confirmations = confirmations
        self.friend_mode = friend_mode
        self.set_mic = set_mic
        self.status = status
        self.say = say
        self.message = message
        self.stop_speaking = stop_speaking
        settings = getattr(brain, "settings", None)
        max_steps = getattr(settings, "agent_max_steps", 5)
        if getattr(settings, "agent_enabled", True) is False:
            max_steps = 1
        stop_on_failure = getattr(settings, "agent_stop_on_failure", True)
        if not isinstance(max_steps, int):
            max_steps = 5
        if not isinstance(stop_on_failure, bool):
            stop_on_failure = True
        self.executor = AgentExecutor(
            actions=actions,
            security=security,
            confirmations=confirmations,
            friend_mode=friend_mode,
            status=status,
            say=say,
            stop_speaking=stop_speaking,
            max_steps=max_steps,
            stop_on_failure=stop_on_failure,
        )

    def process(self, text: str, *, is_owner: bool, source: str) -> str:
        if is_mic_off_command(text):
            if self.confirmations.pending_action:
                self.confirmations.resolve("cancel", is_owner=is_owner)
            self.executor.clear_pending()
            reply = (
                "Theek hai, mic off kar diya. Double-click ya hotkey se "
                "mujhe phir bula lena."
            )
            self.set_mic(False)
            self.say(reply)
            return reply

        pending_result = self._handle_pending_request(
            text,
            is_owner=is_owner,
            source=source,
        )
        if pending_result is not None:
            return pending_result

        self.status("thinking", "Groq is understanding…")
        response = self._shopping_followup(text) or self.brain.understand(text)
        if source == "typed":
            self.message("you", text)
        if response.needs_clarification or not response.actions:
            reply = response.spoken_reply or "Please thoda aur clearly boliye."
            self.say(reply)
            return reply
        return self.executor.execute_plan(
            response.actions,
            is_owner=is_owner,
            source=source,
        )

    def _handle_pending_request(
        self,
        text: str,
        *,
        is_owner: bool,
        source: str,
    ) -> str | None:
        pending = self.confirmations.pending_action
        if pending is None:
            return None

        if self.security.is_negative(text) or self.security.is_confirmation_only(text):
            confirmation = self.confirmations.resolve(text, is_owner=is_owner)
            return (
                self._finish_confirmation(confirmation)
                if confirmation is not None
                else None
            )

        cleaned, contained_confirmation = self._without_confirmation_markers(text)
        corrected = self._parse_pending_correction(cleaned, pending)
        if corrected is not None:
            prompt = self.confirmations.request(corrected, source=source)
            description = action_description(corrected)
            if contained_confirmation:
                reply = (
                    f"Maine pending request {description} ke liye update kar di. "
                    "Purana suna hua contact execute nahi kiya. Safety ke liye "
                    "ab alag se sirf confirm boliye, ya cancel boliye."
                )
            else:
                reply = f"Maine pending request update kar di. {prompt}"
            self.say(reply)
            return reply

        # Keep the older request blocked. In particular, a confirmation word
        # embedded in an unparsed command must never release it.
        confirmation = self.confirmations.resolve(text, is_owner=is_owner)
        if confirmation is None:
            return None
        if contained_confirmation:
            confirmation.message = (
                "Correction clear nahi hui, isliye purani request execute nahi "
                "ki. Contact dobara boliye; sahi naam repeat hone ke baad sirf "
                "confirm boliye."
            )
        return self._finish_confirmation(confirmation)

    def _parse_pending_correction(
        self,
        text: str,
        pending: ActionRequest,
    ) -> ActionRequest | None:
        if not text:
            return None
        local = local_intent(text)
        response = local if local.actions else self.brain.understand(text)
        if (
            response.needs_clarification
            or len(response.actions) != 1
            or response.actions[0].name != pending.name
        ):
            return None
        return response.actions[0]

    @staticmethod
    def _without_confirmation_markers(text: str) -> tuple[str, bool]:
        contained = bool(_STRONG_CONFIRMATION_MARKER.search(text))
        cleaned = _STRONG_CONFIRMATION_MARKER.sub(" ", text)
        previous = None
        while cleaned != previous:
            previous = cleaned
            cleaned = _EDGE_CONFIRMATION_MARKER.sub(" ", cleaned)
        cleaned = " ".join(cleaned.split()).strip(" ,;:-")
        return cleaned, contained

    def _finish_confirmation(
        self, confirmation: ConfirmationResolution
    ) -> str:
        if confirmation.action:
            return self.executor.resume_approved(confirmation.action)
        if confirmation.state in {"denied", "expired", "missing"}:
            self.executor.clear_pending()
        self.say(confirmation.message)
        return confirmation.message

    def _shopping_followup(self, text: str) -> BrainResponse | None:
        action = self.actions.shopping.followup(text)
        return BrainResponse(actions=[action]) if action else None
