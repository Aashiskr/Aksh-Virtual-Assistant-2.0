from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox

from .meeting_overlay import MeetingOverlay


LOGGER = logging.getLogger(__name__)


class MeetingUI:
    def __init__(self, root: tk.Tk, assistant):
        self.root = root
        self.assistant = assistant
        self.overlay = MeetingOverlay(root)
        self.menu: tk.Menu | None = None
        self.menu_index: int | None = None
        self.last_answer_index: int | None = None
        self.last_answer: dict | None = None

    def attach_menu(self, menu: tk.Menu) -> None:
        self.menu = menu
        menu.add_command(
            label=self._menu_label(),
            command=self.toggle,
        )
        self.menu_index = menu.index("end")
        menu.add_command(
            label="Show last meeting answer",
            command=self.show_last_answer,
            state="disabled",
        )
        self.last_answer_index = menu.index("end")
        menu.add_command(
            label="Test answer overlay",
            command=self.test_overlay,
        )

    def refresh_menu(self) -> None:
        if self.menu is not None and self.menu_index is not None:
            self.menu.entryconfigure(
                self.menu_index,
                label=self._menu_label(),
            )
            if self.last_answer_index is not None:
                self.menu.entryconfigure(
                    self.last_answer_index,
                    state="normal" if self.last_answer else "disabled",
                )

    def toggle(self) -> None:
        try:
            if self.assistant.meeting_active:
                self.assistant.stop_meeting_mode()
            else:
                self.assistant.start_meeting_mode()
        except Exception as exc:
            messagebox.showerror(
                "Aksh Meeting Mode",
                str(exc),
                parent=self.root,
            )
        self.refresh_menu()

    def handle(self, event: str, payload: dict) -> None:
        if event == "started":
            detail = (
                "Meeting memory started.\n"
                f"Participant audio: {payload['participant_device']}\n"
                f"Your voice: {payload['owner_device']}"
            )
            self.overlay.show_status("MEETING MODE ACTIVE", detail)
        elif event == "answer":
            LOGGER.info("Displaying private meeting answer overlay")
            self.last_answer = dict(payload)
            self.show_last_answer()
        elif event == "reply_review" and payload.get("needs_correction"):
            self.overlay.show_correction(
                payload["owner_reply"],
                payload["correction"],
                payload["better_answer"],
            )
        elif event == "finished":
            self.overlay.show_report(
                payload["report"],
                payload["markdown_path"],
            )
        elif event == "error":
            self.overlay.show_error(payload.get("message", "Unknown error"))
        self.refresh_menu()

    def show_last_answer(self) -> None:
        if not self.last_answer:
            return
        self.overlay.show_answer(
            self.last_answer["question"],
            self.last_answer["answer"],
            self.last_answer.get("key_points", []),
        )

    def test_overlay(self) -> None:
        self.overlay.show_answer(
            "Can you see this private answer window?",
            (
                "Yes. Live meeting answers will appear in this same window. "
                "It stays visible locally and is excluded from supported "
                "screen-capture APIs."
            ),
            ["Drag the header to move it", "Right-click → Show last answer"],
        )

    def _menu_label(self) -> str:
        return (
            "Stop Meeting Mode"
            if self.assistant.meeting_active
            else "Start Meeting Mode"
        )
