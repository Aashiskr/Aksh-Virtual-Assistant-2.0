from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from .capture_privacy import set_capture_excluded
from .theme import (
    ACCENT,
    ACCENT_HOVER,
    BORDER,
    MUTED,
    PANEL_BG,
    SURFACE,
    SWITCH_OFF,
    TEXT,
)


class SlideSwitch(tk.Canvas):
    """Compact keyboard-accessible ON/OFF slider for Tkinter."""

    WIDTH = 52
    HEIGHT = 28

    def __init__(
        self,
        parent: tk.Misc,
        *,
        value: bool,
        command: Callable[[bool], None],
    ) -> None:
        super().__init__(
            parent,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg=parent.cget("bg"),
            cursor="hand2",
            highlightthickness=0,
            takefocus=True,
        )
        self._value = bool(value)
        self._command = command
        self.bind("<Button-1>", self._toggle_event)
        self.bind("<space>", self._toggle_event)
        self.bind("<Return>", self._toggle_event)
        self.bind("<FocusIn>", lambda _event: self._draw(focused=True))
        self.bind("<FocusOut>", lambda _event: self._draw())
        self._draw()

    @property
    def value(self) -> bool:
        return self._value

    def set(self, value: bool, *, notify: bool = False) -> None:
        changed = self._value != bool(value)
        self._value = bool(value)
        self._draw(focused=self.focus_get() is self)
        if notify and changed:
            self._command(self._value)

    def _toggle_event(self, _event=None) -> str:
        self.set(not self._value, notify=True)
        return "break"

    def _draw(self, *, focused: bool = False) -> None:
        self.delete("all")
        height = self.HEIGHT
        width = self.WIDTH
        track = ACCENT if self._value else SWITCH_OFF
        outline = ACCENT_HOVER if focused else track
        radius = height // 2
        self.create_oval(1, 1, height - 1, height - 1, fill=track, outline=outline)
        self.create_oval(
            width - height + 1,
            1,
            width - 1,
            height - 1,
            fill=track,
            outline=outline,
        )
        self.create_rectangle(
            radius,
            1,
            width - radius,
            height - 1,
            fill=track,
            outline=track,
        )
        knob_left = width - height + 4 if self._value else 4
        self.create_oval(
            knob_left,
            4,
            knob_left + height - 8,
            height - 4,
            fill="#ffffff",
            outline="#ffffff",
        )


class SettingsPanel:
    def __init__(
        self,
        root: tk.Tk,
        settings,
        *,
        on_wake: Callable[[bool], None],
        on_double_clap: Callable[[bool], None],
        on_continuous: Callable[[bool], None],
        on_enroll: Callable[[], None],
    ) -> None:
        self.root = root
        self.settings = settings
        self.callbacks = {
            "wake": on_wake,
            "double_clap": on_double_clap,
            "continuous": on_continuous,
        }
        self.on_enroll = on_enroll
        self.window: tk.Toplevel | None = None
        self.switches: dict[str, SlideSwitch] = {}
        self.state_labels: dict[str, tk.Label] = {}

    def show(self, anchor_x: int, anchor_y: int) -> None:
        if self.window and self.window.winfo_exists():
            self.refresh()
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            return
        self._build(anchor_x, anchor_y)
        self.refresh()

    def refresh(self) -> None:
        values = {
            "wake": bool(self.settings.wake_listener_enabled),
            "double_clap": bool(self.settings.double_clap_enabled),
            "continuous": bool(self.settings.continuous_listening_enabled),
        }
        for key, value in values.items():
            switch = self.switches.get(key)
            if switch:
                switch.set(value)
            label = self.state_labels.get(key)
            if label:
                label.configure(
                    text="ON" if value else "OFF",
                    fg=ACCENT if value else MUTED,
                )

    def _build(self, anchor_x: int, anchor_y: int) -> None:
        window = tk.Toplevel(self.root)
        self.window = window
        window.title("Aksh Settings")
        window.configure(bg=PANEL_BG)
        window.geometry(
            f"560x470+{max(20, anchor_x - 310)}+{max(20, anchor_y - 260)}"
        )
        window.resizable(False, False)
        window.attributes("-topmost", True)
        window.protocol("WM_DELETE_WINDOW", window.withdraw)
        self.root.after(30, lambda: set_capture_excluded(window))

        header = tk.Frame(window, bg=PANEL_BG)
        header.pack(fill="x", padx=28, pady=(24, 8))
        tk.Label(
            header,
            text="Settings",
            bg=PANEL_BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 20),
        ).pack(side="left")
        tk.Button(
            header,
            text="Close",
            command=window.withdraw,
            bg=SURFACE,
            fg=TEXT,
            activebackground="#e4e7e3",
            activeforeground=TEXT,
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=6,
        ).pack(side="right")
        tk.Label(
            window,
            text="Voice activation ko clearly control karein.",
            bg=PANEL_BG,
            fg=MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=28, pady=(0, 16))

        self._setting_row(
            window,
            "wake",
            "Microphone listening",
            "Sirf configured wake phrase se Aksh ko activate kare.",
        )
        self._setting_row(
            window,
            "double_clap",
            "Double clap to talk",
            "Do claps ke baad ek protected command session khole.",
        )
        self._setting_row(
            window,
            "continuous",
            "Always listen",
            "Wake word ke bina sunta hai · music ke saath OFF recommended.",
        )

        footer = tk.Frame(window, bg=PANEL_BG)
        footer.pack(fill="x", padx=28, pady=(10, 22))
        lock_state = "ON" if self.settings.voice_lock_enabled else "OFF"
        tk.Label(
            footer,
            text=f"Owner voice lock: {lock_state}",
            bg=PANEL_BG,
            fg=ACCENT if self.settings.voice_lock_enabled else MUTED,
            font=("Segoe UI Semibold", 9),
        ).pack(side="left")
        if self.settings.voice_lock_enabled:
            tk.Button(
                footer,
                text="Enroll voice",
                command=self.on_enroll,
                bg=ACCENT,
                fg="#ffffff",
                activebackground=ACCENT_HOVER,
                activeforeground="#ffffff",
                relief="flat",
                cursor="hand2",
                padx=14,
                pady=6,
            ).pack(side="right")

    def _setting_row(
        self,
        parent: tk.Misc,
        key: str,
        title: str,
        description: str,
    ) -> None:
        card = tk.Frame(
            parent,
            bg=SURFACE,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        card.pack(fill="x", padx=28, pady=6, ipady=12)
        text = tk.Frame(card, bg=SURFACE)
        text.pack(side="left", fill="both", expand=True, padx=(16, 8))
        tk.Label(
            text,
            text=title,
            bg=SURFACE,
            fg=TEXT,
            font=("Segoe UI Semibold", 11),
        ).pack(anchor="w")
        tk.Label(
            text,
            text=description,
            bg=SURFACE,
            fg=MUTED,
            font=("Segoe UI", 9),
            wraplength=360,
            justify="left",
        ).pack(anchor="w", pady=(3, 0))

        controls = tk.Frame(card, bg=SURFACE)
        controls.pack(side="right", padx=(8, 16))
        state = tk.Label(
            controls,
            text="OFF",
            bg=SURFACE,
            fg=MUTED,
            font=("Segoe UI Semibold", 8),
            width=4,
        )
        state.pack(pady=(0, 4))
        switch = SlideSwitch(
            controls,
            value=False,
            command=lambda value, selected=key: self._changed(selected, value),
        )
        switch.pack()
        self.state_labels[key] = state
        self.switches[key] = switch

    def _changed(self, key: str, value: bool) -> None:
        self.callbacks[key](value)
        self.refresh()
