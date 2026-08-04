from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence

from ..actions import ActionRegistry
from .catalog import TERMINAL_ACTION_NAMES
from ..confirmations import ConfirmationManager
from ..models import ActionRequest, ActionResult
from ..permissions import FriendModeController, action_description
from ..security import SecurityManager


LOGGER = logging.getLogger(__name__)


class AgentExecutor:
    """Runs a validated, bounded action plan through Aksh's approved tools."""

    def __init__(
        self,
        *,
        actions: ActionRegistry,
        security: SecurityManager,
        confirmations: ConfirmationManager,
        friend_mode: FriendModeController,
        status: Callable[[str, str], None],
        say: Callable[[str], None],
        stop_speaking: Callable[[], None],
        max_steps: int = 5,
        stop_on_failure: bool = True,
    ):
        self.actions = actions
        self.security = security
        self.confirmations = confirmations
        self.friend_mode = friend_mode
        self.status = status
        self.say = say
        self.stop_speaking = stop_speaking
        self.max_steps = max(1, min(10, int(max_steps)))
        self.stop_on_failure = stop_on_failure
        self._pending_tail: list[ActionRequest] = []
        self._pending_context: tuple[bool, str] | None = None
        self._lock = threading.RLock()

    def execute_plan(
        self,
        actions: Sequence[ActionRequest],
        *,
        is_owner: bool,
        source: str,
    ) -> str:
        plan = list(actions[: self.max_steps])
        if len(actions) > len(plan):
            LOGGER.warning(
                "Agent plan truncated from %d to %d steps",
                len(actions),
                self.max_steps,
            )
        self.clear_pending()
        return self._run(plan, is_owner=is_owner, source=source)

    def resume_approved(self, action: ActionRequest) -> str:
        with self._lock:
            tail = self._pending_tail
            context = self._pending_context or (True, "confirmation")
            self._pending_tail = []
            self._pending_context = None
        is_owner, source = context
        return self._run(
            [action, *tail],
            is_owner=is_owner,
            source=source,
            approved_first=True,
        )

    def clear_pending(self) -> None:
        with self._lock:
            self._pending_tail = []
            self._pending_context = None

    def _run(
        self,
        plan: list[ActionRequest],
        *,
        is_owner: bool,
        source: str,
        approved_first: bool = False,
    ) -> str:
        reports: list[str] = []
        for index, action in enumerate(plan):
            if action.name == "friend_mode":
                self.friend_mode.handle(action, is_owner=is_owner)
                reports.append("Friends Mode update process ho gaya.")
                continue
            if action.name == "stop":
                self.stop_speaking()
                self.clear_pending()
            needs_approval = (
                not (approved_first and index == 0)
                and self.security.needs_owner_approval(
                    action, is_owner=is_owner
                )
            )
            if needs_approval:
                self._suspend(plan[index + 1 :], is_owner, source)
                prompt = self.confirmations.request(action, source=source)
                self.say(prompt)
                reports.append(prompt)
                break
            result = self._execute(action)
            reports.append(result.message)
            if action.name in TERMINAL_ACTION_NAMES:
                break
            if not result.success and self.stop_on_failure:
                LOGGER.info("Agent plan stopped after failed action %s", action.name)
                break
        return "\n".join(reports)

    def _suspend(
        self, tail: list[ActionRequest], is_owner: bool, source: str
    ) -> None:
        with self._lock:
            self._pending_tail = list(tail)
            self._pending_context = (is_owner, source)

    def _execute(self, action: ActionRequest) -> ActionResult:
        self.status("working", action_description(action))
        result = self.actions.execute(action)
        self.say(result.message)
        return result
