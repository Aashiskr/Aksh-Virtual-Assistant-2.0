from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path

from .capture_privacy import set_capture_excluded
from .theme import (
    ACCENT,
    ACCENT_HOVER,
    DANGER,
    MUTED,
    PANEL_BG,
    SURFACE,
    SURFACE_ALT,
    TEXT,
    WARNING,
)
from .window_behavior import (
    hide_from_taskbar,
    keep_always_on_top,
    set_click_through,
)


REVEAL_DELAY_MILLISECONDS = 100


class MeetingOverlay:
    """Silent, draggable answer/report window excluded from screen capture."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.window: tk.Toplevel | None = None
        self.title_label = None
        self.content = None
        self.copy_button = None
        self.open_button = None
        self.report_path: Path | None = None
        self._drag_origin = None
        self._hide_job = None
        self._reveal_job = None
        self._visible = False

    def show_status(self, title: str, detail: str) -> None:
        self._show(title, detail, accent=ACCENT, compact=True)
        self._schedule_hide(3500)

    def show_answer(
        self, question: str, answer: str, key_points: list[str]
    ) -> None:
        parts = [f"QUESTION\n{question}", "", f"ANSWER\n{answer}"]
        if key_points:
            parts.extend(
                ["", "KEY POINTS", *[f"• {point}" for point in key_points]]
            )
        self._show(
            "AKSH · SUGGESTED ANSWER",
            "\n".join(parts),
            accent=ACCENT,
        )

    def show_correction(
        self, owner_reply: str, correction: str, better_answer: str
    ) -> None:
        body = (
            f"YOUR REPLY\n{owner_reply}\n\n"
            f"CORRECTION\n{correction}\n\n"
            f"BETTER ANSWER\n{better_answer}"
        )
        self._show("AKSH · REPLY CORRECTION", body, accent=WARNING)

    def show_error(self, message: str) -> None:
        self._show("MEETING MODE ISSUE", message, accent=DANGER, compact=True)

    def show_report(self, report: str, path: str) -> None:
        self.report_path = Path(path)
        self._show(
            "AKSH · MEETING REPORT",
            report,
            accent=ACCENT,
            report=True,
        )

    def hide(self) -> None:
        self._cancel_hide()
        self._cancel_reveal()
        if self.window and self.window.winfo_exists():
            self.window.attributes("-alpha", 0.0)
            set_click_through(self.window, True)
            self._visible = False

    def _show(
        self,
        title: str,
        body: str,
        *,
        accent: str,
        compact: bool = False,
        report: bool = False,
    ) -> None:
        self._ensure_window()
        self._cancel_hide()
        self._cancel_reveal()
        assert self.window and self.title_label and self.content
        first_reveal = not self._visible
        if first_reveal:
            self.window.attributes("-alpha", 0.0)
        self.window.geometry("820x640" if report else (
            "620x250" if compact else "680x430"
        ))
        self.title_label.configure(text=title, fg=accent)
        self.content.configure(state="normal")
        self.content.delete("1.0", "end")
        self.content.insert("1.0", body)
        self.content.configure(state="disabled")
        self.open_button.configure(
            state="normal" if report and self.report_path else "disabled"
        )
        self.window.update_idletasks()
        self._ensure_on_screen()
        hide_from_taskbar(self.window)
        set_capture_excluded(self.window)
        keep_always_on_top(self.window)
        if not self.window.winfo_viewable():
            self.window.deiconify()
        if first_reveal:
            self._reveal_job = self.root.after(
                REVEAL_DELAY_MILLISECONDS,
                self._reveal_window,
            )
        self.root.after(150, self._refresh_window_behavior)

    def _ensure_window(self) -> None:
        if self.window and self.window.winfo_exists():
            return
        window = tk.Toplevel(self.root)
        window.withdraw()
        window.attributes("-alpha", 0.0)
        self.window = window
        window.title("Aksh Meeting Assist")
        window.attributes("-topmost", True)
        window.transient(self.root)
        window.configure(bg=PANEL_BG)
        window.geometry(self._initial_geometry())
        window.resizable(True, True)
        window.protocol("WM_DELETE_WINDOW", self.hide)

        header = tk.Frame(window, bg=SURFACE, height=46)
        header.pack(fill="x")
        header.pack_propagate(False)
        self.title_label = tk.Label(
            header,
            text="AKSH · MEETING ASSIST",
            bg=SURFACE,
            fg=ACCENT,
            font=("Segoe UI Semibold", 11),
        )
        self.title_label.pack(side="left", padx=16)
        tk.Button(
            header,
            text="×",
            command=self.hide,
            bg=SURFACE,
            fg=TEXT,
            activebackground=SURFACE_ALT,
            activeforeground=TEXT,
            relief="flat",
            font=("Segoe UI", 14),
        ).pack(side="right", padx=8)
        header.bind("<ButtonPress-1>", self._drag_start)
        header.bind("<B1-Motion>", self._drag_move)
        self.title_label.bind("<ButtonPress-1>", self._drag_start)
        self.title_label.bind("<B1-Motion>", self._drag_move)

        content_frame = tk.Frame(window, bg=PANEL_BG)
        content_frame.pack(fill="both", expand=True, padx=14, pady=(12, 6))
        scrollbar = tk.Scrollbar(content_frame)
        scrollbar.pack(side="right", fill="y")
        self.content = tk.Text(
            content_frame,
            wrap="word",
            bg=PANEL_BG,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground="#b8dcc9",
            relief="flat",
            font=("Segoe UI", 11),
            padx=8,
            pady=8,
            yscrollcommand=scrollbar.set,
        )
        self.content.pack(fill="both", expand=True)
        self.content.configure(state="disabled")
        scrollbar.configure(command=self.content.yview)

        footer = tk.Frame(window, bg=PANEL_BG)
        footer.pack(fill="x", padx=16, pady=(0, 12))
        self.copy_button = self._button(footer, "Copy", self._copy)
        self.copy_button.pack(side="left")
        self.open_button = self._button(
            footer, "Open report", self._open_report
        )
        self.open_button.pack(side="left", padx=8)
        self.open_button.configure(state="disabled")
        tk.Label(
            footer,
            text="Silent · private overlay",
            bg=PANEL_BG,
            fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(side="right")
        hide_from_taskbar(window)
        set_capture_excluded(window)
        set_click_through(window, True)
        window.deiconify()
        window.update_idletasks()

    def _reveal_window(self) -> None:
        self._reveal_job = None
        if not self.window or not self.window.winfo_exists():
            return
        set_click_through(self.window, False)
        self.window.attributes("-alpha", 1.0)
        self._visible = True
        keep_always_on_top(self.window)

    def _refresh_window_behavior(self) -> None:
        if not self.window or not self.window.winfo_exists():
            return
        hide_from_taskbar(self.window)
        keep_always_on_top(self.window)
        set_capture_excluded(self.window)

    def _initial_geometry(self) -> str:
        width, height = 680, 430
        x = max(20, self.root.winfo_screenwidth() - width - 40)
        y = max(20, (self.root.winfo_screenheight() - height) // 2)
        return f"{width}x{height}+{x}+{y}"

    def _ensure_on_screen(self) -> None:
        if not self.window:
            return
        x, y = self.window.winfo_x(), self.window.winfo_y()
        width, height = self.window.winfo_width(), self.window.winfo_height()
        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        visible = (
            x < screen_w - 80
            and y < screen_h - 60
            and x + width > 80
            and y + height > 40
        )
        if not visible:
            self.window.geometry(self._initial_geometry())

    def _button(self, parent, text, command):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=SURFACE_ALT,
            fg=TEXT,
            activebackground=ACCENT_HOVER,
            activeforeground=TEXT,
            relief="flat",
            padx=14,
            pady=5,
        )

    def _copy(self) -> None:
        if not self.content:
            return
        text = self.content.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _open_report(self) -> None:
        if self.report_path and self.report_path.exists():
            os.startfile(self.report_path)

    def _drag_start(self, event) -> None:
        if self.window:
            self._drag_origin = (
                event.x_root,
                event.y_root,
                self.window.winfo_x(),
                self.window.winfo_y(),
            )

    def _drag_move(self, event) -> None:
        if not self.window or not self._drag_origin:
            return
        start_x, start_y, window_x, window_y = self._drag_origin
        self.window.geometry(
            f"+{window_x + event.x_root - start_x}"
            f"+{window_y + event.y_root - start_y}"
        )

    def _schedule_hide(self, milliseconds: int) -> None:
        self._cancel_hide()
        self._hide_job = self.root.after(milliseconds, self.hide)

    def _cancel_hide(self) -> None:
        if self._hide_job is not None:
            self.root.after_cancel(self._hide_job)
            self._hide_job = None

    def _cancel_reveal(self) -> None:
        if self._reveal_job is not None:
            self.root.after_cancel(self._reveal_job)
            self._reveal_job = None
