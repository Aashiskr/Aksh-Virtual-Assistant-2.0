from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence

from ..actions import ActionRegistry
from .catalog import TERMINAL_ACTION_NAMES
from ..confirmations import ConfirmationManager
from ..models import ActionRequest, ActionResult
from ..notebook import SessionTaskNotebook, TaskStatus
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
        notebook: SessionTaskNotebook | None = None,
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
        self.notebook = notebook
        self._pending_tail: list[ActionRequest] = []
        self._pending_context: tuple[bool, str] | None = None
        self._pending_task_id: str | None = None
        self._lock = threading.RLock()

    @property
    def pending_task_id(self) -> str | None:
        with self._lock:
            return self._pending_task_id

    def execute_plan(
        self,
        actions: Sequence[ActionRequest],
        *,
        is_owner: bool,
        source: str,
        task_id: str | None = None,
    ) -> str:
        plan = list(actions[: self.max_steps])
        if len(actions) > len(plan):
            LOGGER.warning(
                "Agent plan truncated from %d to %d steps",
                len(actions),
                self.max_steps,
            )
        self.clear_pending()
        return self._run(
            plan,
            is_owner=is_owner,
            source=source,
            task_id=task_id,
        )

    def resume_approved(self, action: ActionRequest) -> str:
        with self._lock:
            tail = self._pending_tail
            context = self._pending_context or (True, "confirmation")
            task_id = self._pending_task_id
            self._pending_tail = []
            self._pending_context = None
            self._pending_task_id = None
        is_owner, source = context
        return self._run(
            [action, *tail],
            is_owner=is_owner,
            source=source,
            approved_first=True,
            task_id=task_id,
        )

    def clear_pending(self) -> None:
        with self._lock:
            self._pending_tail = []
            self._pending_context = None
            self._pending_task_id = None

    def finish_pending(self, status: TaskStatus, summary: str) -> None:
        with self._lock:
            task_id = self._pending_task_id
            self._pending_tail = []
            self._pending_context = None
            self._pending_task_id = None
        if self.notebook:
            self.notebook.finish(task_id, status, summary, completed_by="user")

    def _run(
        self,
        plan: list[ActionRequest],
        *,
        is_owner: bool,
        source: str,
        approved_first: bool = False,
        task_id: str | None = None,
    ) -> str:
        reports: list[str] = []
        waiting = False
        failed = False
        for index, action in enumerate(plan):
            if action.name == "friend_mode":
                self.friend_mode.handle(action, is_owner=is_owner)
                result = ActionResult(True, "Friends Mode update process ho gaya.")
                reports.append(result.message)
                if self.notebook:
                    self.notebook.record_action_started(task_id, action)
                    self.notebook.record_action_result(task_id, action, result)
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
                self._suspend(plan[index + 1 :], is_owner, source, task_id)
                prompt = self.confirmations.request(action, source=source)
                if self.notebook:
                    self.notebook.record_waiting_confirmation(
                        task_id, action, prompt
                    )
                self.say(prompt)
                reports.append(prompt)
                waiting = True
                break
            if self.notebook:
                self.notebook.record_action_started(task_id, action)
            result = self._execute(action)
            if self.notebook:
                self.notebook.record_action_result(task_id, action, result)
            reports.append(result.message)
            if not result.success:
                failed = True
            if action.name in TERMINAL_ACTION_NAMES:
                break
            if not result.success and self.stop_on_failure:
                LOGGER.info("Agent plan stopped after failed action %s", action.name)
                break
        report = "\n".join(reports)
        if self.notebook and not waiting:
            self.notebook.finish(
                task_id,
                TaskStatus.FAILED if failed else TaskStatus.COMPLETED,
                report,
                completed_by="aksh",
            )
        return report

    def _suspend(
        self,
        tail: list[ActionRequest],
        is_owner: bool,
        source: str,
        task_id: str | None,
    ) -> None:
        with self._lock:
            self._pending_tail = list(tail)
            self._pending_context = (is_owner, source)
            self._pending_task_id = task_id

    def _execute(self, action: ActionRequest) -> ActionResult:
        self.status("working", action_description(action))
        result = self.actions.execute(action)
        self.say(result.message)
        return result
