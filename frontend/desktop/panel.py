from __future__ import annotations

import tkinter as tk
from typing import Callable

from .theme import (
    ACCENT,
    ACCENT_HOVER,
    BORDER,
    PANEL_BG,
    SURFACE,
    SURFACE_ALT,
    TEXT,
)
from .capture_privacy import set_capture_excluded


class CommandPanel:
    def __init__(
        self,
        root: tk.Tk,
        on_talk: Callable[[], None],
        on_send: Callable[[str], None],
        on_enroll: Callable[[], None],
        allow_enrollment: bool = True,
    ):
        self.root = root
        self.on_talk = on_talk
        self.on_send = on_send
        self.on_enroll = on_enroll
        self.allow_enrollment = allow_enrollment
        self.window: tk.Toplevel | None = None

    def show(self, anchor_x: int, anchor_y: int) -> None:
        if self.window and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            return
        panel = tk.Toplevel(self.root)
        self.window = panel
        panel.title("Talk to Aksh")
        panel.attributes("-topmost", True)
        panel.configure(bg=PANEL_BG)
        panel.resizable(False, False)
        panel.geometry(f"390x170+{max(0, anchor_x - 150)}+{max(0, anchor_y - 90)}")
        self.root.after(30, lambda: set_capture_excluded(panel))

        tk.Label(
            panel,
            text="What should Aksh do?",
            bg=PANEL_BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 13),
        ).pack(anchor="w", padx=18, pady=(16, 8))
        entry = tk.Entry(
            panel,
            bg=SURFACE,
            fg=TEXT,
            insertbackground=TEXT,
            relief="solid",
            bd=1,
            highlightbackground=BORDER,
            font=("Segoe UI", 11),
        )
        entry.pack(fill="x", padx=18, ipady=8)
        entry.focus_set()

        def send(event=None) -> None:
            text = entry.get().strip()
            if text:
                self.on_send(text)
                entry.delete(0, "end")

        entry.bind("<Return>", send)
        buttons = tk.Frame(panel, bg=PANEL_BG)
        buttons.pack(fill="x", padx=18, pady=14)
        self._button(buttons, "Talk", self.on_talk, ACCENT).pack(side="left")
        self._button(buttons, "Send", send, SURFACE_ALT).pack(side="left", padx=8)
        if self.allow_enrollment:
            self._button(
                buttons, "Enroll voice", self.on_enroll, SURFACE_ALT
            ).pack(side="right")

    @staticmethod
    def _button(parent, label, command, background):
        accent = background == ACCENT
        return tk.Button(
            parent,
            text=label,
            command=command,
            bg=background,
            fg="#ffffff" if accent else TEXT,
            activebackground=ACCENT_HOVER if accent else "#dfe3de",
            activeforeground="#ffffff" if accent else TEXT,
            relief="flat",
            padx=16,
            pady=6,
        )
